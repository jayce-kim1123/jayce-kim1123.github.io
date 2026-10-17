# 썸네일 스케치 도구

글마다 손으로 그린 노트 스케치 풍 이미지(1200x675 JPEG)를 만든다. Pillow만 필요하다 (`pip install pillow`).
`_` 로 시작하는 폴더라 Jekyll 빌드에는 포함되지 않는다.

```bash
python3 _tools/sketch.py _tools/specs/<글파일명>.json assets/img/philosophy/<글파일명>.jpg
```

* `<글파일명>` = `철학/` 안의 글 파일명에서 `.md`만 뺀 것 (예: `2026-09-02-니체-영원회귀`).
* 이미지가 `assets/img/philosophy/<글파일명>.jpg` 에 있으면 목록 썸네일과 글 상단 삽화로 자동 연결된다. 글 front matter는 건드리지 않는다.
* 스펙(JSON)도 `_tools/specs/` 에 같이 커밋해 둔다.

## 스펙 형식

공통 키: `title`(좌상단 큰 제목, 8자 이내 권장), `caption`(하단 한 줄, 20자 이내 권장). 둘 다 생략 가능.
`template` 은 `flow` `versus` `hub` `free` 중 하나 (기본 `free`). 좌표계는 1200x675, 좌상단이 (0,0).
`hl` 은 형광펜 색: `yellow` `pink` `green` `blue` `orange`.

### flow — 순서/과정 (노드 2~6개, `edges` 라벨은 4자 이내)
```json
{"template":"flow","title":"귀납","nodes":[{"text":"관찰","sub":"까마귀 100마리"},{"text":"일반화","hl":"yellow"},{"text":"예측"}],"edges":["그러니까","그래서"],"caption":"정당화는 어디서?"}
```

### versus — 두 입장 대비
```json
{"template":"versus","title":"맹자 vs 순자","left":{"title":"성선설","hl":"yellow","items":["본래 선하다","환경이 망친다"]},"right":{"title":"성악설","hl":"pink","items":["본래 이기적","예로 다듬는다"]},"vs":"vs","caption":"둘 다 고정된 본성을 전제"}
```

### hub — 중심 개념과 관계 (주변 노드 3~6개)
```json
{"template":"hub","title":"인간 = 사이","center":{"text":"나","hl":"yellow"},"nodes":["가족","친구",{"text":"사회","edge":"속한다"}],"arrows":false}
```

### free — 직접 배치 (상징적인 그림이 필요할 때)
`elements` 배열에 아래 요소를 원하는 좌표에 놓는다. 제목이 있으면 y≈170 아래부터, 캡션이 있으면 y≈580 위까지 쓴다.

| type | 필드 |
|---|---|
| `box` / `ellipse` | `x y w h`, 선택 `text` `sub` `hl` (ellipse는 text가 있으면 글자 포함) |
| `text` | `x y text`, 선택 `size w h align(left\|center) hl` (w를 주면 자동 줄바꿈·축소) |
| `line` | `from[x,y] to[x,y]`, 선택 `width` |
| `arrow` | `from to`, 선택 `label curve(-0.3~0.3)` |
| `poly` | `points[[x,y]...]`, 선택 `closed` (직선 꺾은선) |
| `curve` | `points[[x,y]...]` (부드러운 곡선, 날개·파도·바가지 등) |
| `figure` | `x y`(발 위치), 선택 `s`(배율, 1≈높이 73px) `label` — 막대 인간 |
| `scribble` | `x y rx ry`, 선택 `gap` — 타원 안을 빽빽이 칠함 (까만 물체, 그림자, 눈) |
| `hatch` | `x y w h`, 선택 `gap` — 대각선 빗금 |
| `sun` | `x y r` |
| `squiggle` | `x y w` — 물결 밑줄 |

예 (새장): `curve` 로 지붕, `line` 여러 개로 살, `ellipse` 로 새 몸통, `poly closed` 로 부리와 꼬리.

## 이미지 원칙

* 목록 카드에서는 폭 350px 정도로 줄어 보인다. **글자는 짧게(한 덩어리 10자 안팎), 요소는 6~10개 이내**로 크게 그린다.
* 글의 핵심 구도를 한눈에 보여주는 그림: 대립 구조(versus), 딜레마 삼각형, 관계도(hub), 상징 장면(새장, 동굴, 나비, 까마귀 등).
* 글자는 반드시 이 도구의 손글씨 폰트로만 쓴다. 그라데이션·그림자·완벽한 대칭·장식은 넣지 않는다.
* 실존 인물의 얼굴/초상, 저작권 있는 그림은 그리지 않는다. 막대 인간과 단순한 사물만 쓴다.
* 생성 후 반드시 이미지를 열어 확인한다: 글자가 겹치거나 상자 밖으로 나가지 않는지, 요소가 서로 가리지 않는지.
