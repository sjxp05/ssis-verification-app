### 실행 방법

1. venv 환경 세팅

    ```pwsh
    python -m venv .venv
    ```

2. venv 가상환경 활성화\
   (\* 3, 4는 활성화 시킨 상태에서 실행해야 됨!)

    ```bash
     .venv\Scripts\Activate # Windows
     source .venv/bin/activate # Mac
    ```

3. 필요한 라이브러리 다운로드

    ```pwsh
    pip install -r requirements.txt
    ```

4. main.py 실행

    ```pwsh
    python app/main.py
    ```

5. 수정하다가 추가로 설치한 라이브러리가 있으면 다음 명령어 실행
    ```pwsh
    pip freeze > requirements.txt
    ```
