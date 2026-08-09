"""어휘 축소 — 임베딩 테이블에서 쓰지 않는 문자 체계를 제거한다. (빌드 타임 전용)

원본 e5-small 의 어휘는 250,002개이고 그중 한글은 2.2%뿐이다.
임베딩 테이블이 모델의 82%를 차지하므로, 쓰지 않을 체계를 덜어내면 용량이 크게 준다.

채택 수위는 T3 (한글 + ASCII 라틴 + 중립). 실측 결과 원본과 임베딩 코사인
일치도가 1.0000 으로 **손실이 0** 이면서 용량은 52% 감소한다. 우리 라벨이
한글·숫자·일부 ASCII 로만 구성되므로 한자·가나·악센트 라틴 토큰은 애초에
선택되지 않기 때문이다.

한 단계 더(T4, 다문자 라틴 제거)는 일치도가 0.848로 떨어진다.
e5 가 요구하는 `query: ` 프리픽스가 라틴 문자열이라 함께 깨지기 때문이다.
"""

from __future__ import annotations

import json
import unicodedata

import torch

# 유니코드 문자명 접두사로 체계를 판별한다. 코드포인트 범위를 열거하면
# 확장 영역(CJK Ext, Hangul Jamo Extended 등)에서 누락이 생긴다.
_NAME_PREFIX = [
    ("HANGUL", "hangul"),
    ("CJK", "hanja"),
    ("KATAKANA", "kana"),
    ("HIRAGANA", "kana"),
    ("LATIN", "latin"),
]

# 어느 언어에도 귀속되지 않는 공통 문자. 항상 보존한다.
_NEUTRAL = {"digit", "punct", "symbol", "space", "meta", "empty", "unknown"}

# 채택 수위 T3
ALLOWED_SCRIPTS = {"hangul", "latin"}
ASCII_ONLY_LATIN = True


def _char_script(ch: str) -> str:
    if ch == "▁":  # SentencePiece 어절 경계 표식
        return "meta"
    cat = unicodedata.category(ch)
    if cat == "Nd" or ch.isdigit():
        return "digit"
    if cat.startswith("Z") or ch.isspace():
        return "space"
    if cat.startswith("P"):
        return "punct"
    if cat[0] in "SMC":
        return "symbol"
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return "unknown"
    for prefix, label in _NAME_PREFIX:
        if name.startswith(prefix):
            return label
    return "other"


def _token_scripts(token: str) -> set[str]:
    return {_char_script(c) for c in token} or {"empty"}


def build_keep_ids(vocab) -> list[int]:
    """보존할 토큰 id. 원래 순서를 유지하므로 재매핑이 위치로 결정된다.

    안전 규칙 두 가지를 항상 지킨다.
      - 특수 토큰(<s> <pad> </s> <unk> <mask>)은 무조건 보존
      - **길이 1인 토큰은 문자 체계와 무관하게 무조건 보존**
        Unigram 은 긴 토큰이 없으면 짧은 토큰으로 분해하므로, 단일 문자만
        남아 있으면 미지 입력이 <unk> 로 떨어지지 않는다. 한자를 제거해도
        한자가 등장하면 문자 단위로는 처리된다는 뜻이다.
    """
    keep = []
    for i, entry in enumerate(vocab):
        token = entry[0]
        if i < 4 or i == len(vocab) - 1:
            keep.append(i)
            continue

        body = token.replace("▁", "")
        if len(body) <= 1:
            keep.append(i)
            continue

        scripts = _token_scripts(token) - _NEUTRAL
        if not scripts:
            keep.append(i)
            continue
        if not scripts <= ALLOWED_SCRIPTS:
            continue
        if ASCII_ONLY_LATIN and "latin" in scripts:
            if not all(ord(c) < 128 or c == "▁" for c in token):
                continue
        keep.append(i)
    return keep


def prune_tokenizer(tokenizer_json: dict, keep_ids: list[int]) -> dict:
    """어휘를 잘라내고 특수 토큰 id 를 재매핑한 tokenizer.json 을 만든다."""
    out = json.loads(json.dumps(tokenizer_json))
    old_vocab = tokenizer_json["model"]["vocab"]
    out["model"]["vocab"] = [old_vocab[i] for i in keep_ids]

    remap = {old: new for new, old in enumerate(keep_ids)}
    out["model"]["unk_id"] = remap[tokenizer_json["model"]["unk_id"]]
    for added in out.get("added_tokens", []):
        added["id"] = remap[added["id"]]
    post = out.get("post_processor") or {}
    for spec in (post.get("special_tokens") or {}).values():
        spec["ids"] = [remap[i] for i in spec["ids"]]
    return out


def prune_model(model, keep_ids: list[int]):
    """임베딩 행을 keep_ids 순서로 잘라낸다.

    양자화 이전, torch 단계에서 수행해야 한다. 양자화된 ONNX 그래프를 직접
    수술하면 scale·zero_point 까지 함께 손봐야 해서 위험하다.
    """
    emb = model.embeddings.word_embeddings
    pruned = torch.nn.Embedding(len(keep_ids), emb.embedding_dim, padding_idx=emb.padding_idx)
    pruned.weight.data = emb.weight.data[torch.tensor(keep_ids, dtype=torch.long)].clone()
    model.embeddings.word_embeddings = pruned
    model.config.vocab_size = len(keep_ids)
    return model
