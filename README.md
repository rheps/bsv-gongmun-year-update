# bsv-gongmun-year-update

작년 공문과 첨부 파일을 이번 학년도 버전으로 바꾸는 스킬입니다. Windows에서 Claude Code, Codex, Antigravity로 쓸 수 있습니다.

## 설치

Windows 명령 프롬프트(cmd)를 열고 아래 줄을 붙여 넣은 뒤 Enter를 누르세요.

```
curl -fsSL https://raw.githubusercontent.com/rheps/bsv-gongmun-year-update/main/install.cmd -o install.cmd && install.cmd && del install.cmd
```

설치 프로그램은 Python을 확인하고 필요한 Python 패키지를 설치한 뒤, 스킬을 Claude Code, Codex, Antigravity의 스킬 폴더에 복사합니다. 업데이트할 때 다시 실행해도 됩니다.

## 예시 공문으로 해 보기

아래 줄을 실행하면 지금 폴더에 예시 폴더 작년공문을 내려받습니다. 예시는 꾸며 낸 공문이며 오타를 일부러 넣었습니다.

```
curl -fsSL -o sample-gongmun.zip https://raw.githubusercontent.com/rheps/bsv-gongmun-year-update/main/examples/sample-gongmun.zip && tar -xf sample-gongmun.zip && del sample-gongmun.zip
```

그 폴더에서 Claude Code, Codex 또는 Antigravity를 열고 이렇게 요청하세요.

> 작년공문 폴더를 올해 공문으로 바꿔 줘

그 옆에 새 폴더 작년공문_올해버전이 생깁니다. 이 폴더에는 바꾼 파일, 검토표.xlsx(검토표)와 전후캡처비교.html(바꾸기 전과 후의 쪽을 나란히 놓은 페이지)이 들어 있습니다. 원본 파일은 바꾸지 않습니다.

## 하는 일

- 날짜를 같은 주, 같은 요일로 이번 학년도에 옮깁니다. 옮긴 날이 공휴일이나 주말이면 가장 가까운 평일로 옮깁니다.
- hwp와 글자 PDF를 hwpx로 바꾸고, 공문 본문(odt)은 「1. 관련:」 줄을 넣어 업무관리시스템에 붙여 넣을 글로 바꿉니다.
- 관련 줄의 문서번호는 OOOO, 날짜는 OO. OO.로 바꿔 두니 실제 값을 채우세요.
- 오타, 띄어쓰기, 표기(빨간색)를 고치고 어색한 문장(파란색)을 다듬은 뒤, 고친 곳을 모두 비교 페이지에 표시합니다.
- 이름, 금액, 문서번호, 순서가 바뀐 날짜처럼 직접 확인할 곳은 「확인할 곳」 시트에 적습니다.
- 학생 자료로 보이는 파일은 바꾸지 않고 학생자료_변환안함에 그대로 복사합니다. 이 파일은 변환하지도, 윤문하지도, 비교 페이지에 보여 주지도 않습니다.

## 필요한 것

- Windows 10 또는 11
- Python 3.10 이상. 설치하려면 cmd에서 다음을 실행하세요. `winget install Python.Python.3.14`
- 한글(한컴오피스) 2020 이상. hwp 파일을 열고 쪽 그림을 만들 때 필요합니다.
- LibreOffice(선택). xls 파일을 변환하고 odt, docx, xlsx 파일의 쪽 그림을 만듭니다. 없으면 xls 파일은 그대로 복사합니다.
- Claude Code, Codex 또는 Antigravity
- kiwipiepy는 자동으로 설치합니다. 설치하지 못하면 문장 검사가 더 단순한 규칙을 쓰고, 고친 곳을 더 많이 막습니다.

## 개인정보

- 변환 도구는 이 컴퓨터에서만 작동하며 인터넷으로 아무것도 보내지 않습니다.
- 윤문할 때는 사용하는 CLI의 AI 모델이 문서 글을 읽습니다. CLI에 다른 파일을 줄 때와 같습니다. 학교에서 그 AI 서비스에 써도 된다고 허용한 문서에만 쓰세요.
- 학생 자료로 보이는 파일은 윤문하려고 읽지 않습니다. 그래도 실행하기 전에 폴더를 확인해 학생 기록은 빼 두세요.

## 공휴일

공식 자료로 확인한 2025~2027년 공휴일 목록이 들어 있어 2025, 2026학년도를 처리할 수 있습니다. 그 뒤 학년도에는 도구가 멈추고 새 공휴일 목록을 요청합니다. 새 목록이 나오면 스킬을 업데이트하세요.

## 학교마다 다른 낱말(선택)

이전 학교 이름이나 학교 표어 같은 낱말을 검토표에 적게 하려면, 아래 폴더의 표시규칙_예시.json을 표시규칙.json으로 복사하고 낱말을 넣으세요.

```
%USERPROFILE%\.bsv-gongmun-year-update
```

## 업데이트와 삭제

업데이트하려면 설치 줄을 다시 실행하세요. 삭제하려면 아래 세 스킬 폴더에서 각각 bsv-gongmun-year-update 폴더를 지우세요.

```
%USERPROFILE%\.claude\skills\bsv-gongmun-year-update
%USERPROFILE%\.codex\skills\bsv-gongmun-year-update
%USERPROFILE%\.gemini\config\skills\bsv-gongmun-year-update
```
