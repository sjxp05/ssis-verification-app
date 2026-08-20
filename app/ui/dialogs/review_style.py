# 라벨 검토 화면 전용 스타일
#
# app.qss 를 건드리지 않고 이 화면에만 적용한다. 위젯에 건 스타일시트는 앱 전역
# 스타일과 합쳐지므로, Card·PrimaryButton 같은 공용 규칙은 그대로 살아 있고
# 여기 정의한 #Review*·#Preview* 만 얹힌다.
#
# 색은 전부 theme 토큰을 쓴다. 테마가 바뀌면 이 화면도 따라간다.

from __future__ import annotations

from resources.styles import theme

STYLESHEET = f"""
#ReviewFooter {{
    background: {theme.SURFACE};
    border-top: 1px solid {theme.BORDER};
}}

/* 안내 띠. 여백은 레이아웃이 주므로 여기서 padding 을 주지 않는다.
   wordWrap 라벨에 padding 을 주면 Qt 가 높이 계산에서 그 여백을 빠뜨린다. */
#ReviewBanner {{
    border-radius: {theme.RADIUS_SM};
    background: {theme.STEP_BG};
    border: 1px solid {theme.BORDER};
}}
#ReviewBanner[state="warn"] {{
    background: #FFF8E6;
    border: 1px solid #F0D9A0;
}}
#ReviewBanner[state="danger"] {{
    background: {theme.DANGER_BG};
    border: 1px solid {theme.DANGER_BORDER};
}}
#ReviewBanner[state="info"] {{
    background: #F2F7FD;
    border: 1px solid {theme.ACCENT_SOFT};
}}
#ReviewBannerText {{
    font-size: 12px;
    color: {theme.TEXT};
    background: transparent;
    border: none;
}}
#ReviewBanner[state="warn"] #ReviewBannerText {{ color: #7A5A10; }}
#ReviewBanner[state="danger"] #ReviewBannerText {{ color: {theme.DANGER_DARK}; }}
#ReviewBanner[state="info"] #ReviewBannerText {{ color: {theme.ACCENT}; }}

/* 후보 선택지와 점수 */
#ReviewChoice {{
    font-size: 13px;
    color: {theme.TEXT};
    spacing: 8px;
}}
#ReviewChoice:checked {{
    font-weight: 700;
    color: {theme.NAVY};
}}
#ReviewScore {{
    font-family: {theme.FONT_MONO};
    font-size: 11px;
    color: {theme.TEXT_MUTED};
}}

/* 구획 제목과 접기 버튼 */
#ReviewSectionTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {theme.TEXT};
    margin-top: 6px;
}}
#ReviewSectionHint {{
    font-size: 12px;
    color: {theme.TEXT_MUTED};
}}
QToolButton#ReviewToggle {{
    background: transparent;
    border: none;
    color: {theme.NAVY};
    font-size: 13px;
    font-weight: 700;
    text-align: left;
    padding: 6px 0;
}}
QToolButton#ReviewToggle:hover {{
    color: {theme.ACCENT};
}}

/* 조견표 미리보기 */
#PreviewCaption {{
    font-size: 11px;
    font-weight: 700;
    color: {theme.TEXT_MUTED};
}}
QTableWidget#PreviewTable {{
    background: {theme.SURFACE};
    border: 1px solid {theme.BORDER};
    border-radius: {theme.RADIUS_SM};
    gridline-color: {theme.GRID};
    font-size: 11px;
}}
QTableWidget#PreviewTable::item {{
    padding: 2px 6px;
}}
#PreviewEmpty {{
    font-size: 11px;
    color: {theme.TEXT_MUTED};
    padding: 24px 0;
}}
"""
