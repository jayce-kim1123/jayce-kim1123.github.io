---
title: "고객사용 API를 만들며 정해야 했던 것들"
date: 2026-05-18 21:05:45 +0900
categories: [backend]
tags: [django, rest-framework, api-design, redis]
---

고객사가 자기 시스템에서 직접 우리 데이터를 조회할 수 있도록 고객사용 API를 서비스화하는 작업을 진행했다. 내부용 API와 다르게 한 번 공개하면 마음대로 스펙을 바꿀 수 없다는 전제가 붙는다. 그래서 기능을 만들기 전에 버전 관리, 인증, 사용량 제한부터 어떻게 할지 정하는 데 시간을 더 썼다.

## 버전 관리 - URI 대신 쿼리 파라미터

처음엔 `/v1/tickets` 같은 URI 기반 버전 관리를 생각했는데, 고객사마다 필요한 시점과 요구사항이 달라질 걸 감안하면 URI 방식은 버전이 늘어날수록 라우팅과 문서가 같이 불어난다. 그래서 쿼리 파라미터 기반 시맨틱 버저닝(semver)으로 정했다.

- 메이저 버전이 바뀌면 View 클래스와 테스트 클래스를 아예 분리한다.
- 마이너/패치 버전은 같은 View 안에서 분기 처리하고, 테스트는 버전을 명시한 메서드를 추가해서 변경된 부분만 검증한다.
- 기존에 이미 나가 있던 URI 방식 엔드포인트는 죽이지 않고 유지하되, 접근하면 경고 로그를 남기도록 했다.

```python
class PublicApiVersioning(QueryParameterVersioning):
    def determine_version(self, request, *args, **kwargs):
        path = getattr(request, "path", "")
        # TODO: 구버전 엔드포인트 삭제시 아래 분기문 삭제
        if path == "/v1" or path.startswith("/v1/"):
            logger.warning(f"Deprecated endpoint accessed. path={path}")
            determined_version = self.default_version
        else:
            ...
```

semver 정규식으로 버전 문자열 자체도 검증하도록 했다. 잘못된 버전 문자열이 들어오면 그냥 기본값으로 넘기는 대신 404로 명시적으로 거부한다.

## 인증 - 커스텀 헤더 서명 방식

인증은 액세스 키/시크릿 키 쌍을 발급하고, 요청마다 HMAC 서명을 커스텀 헤더 3종(액세스 키, 타임스탬프, 서명)에 담아 보내는 방식을 썼다. 서명은 액세스 키와 타임스탬프를 개행으로 이어붙인 문자열을 시크릿 키로 HMAC-SHA256 해시한 값이다. 타임스탬프는 서버 시각 기준 앞뒤 5분을 벗어나면 거부해서, 탈취된 요청을 그대로 재전송(replay)하는 공격의 유효 시간을 좁혔다.

## 사용량 제한 - Redis 기반, 티어별로 다르게

과금 등급(티어)에 따라 API 사용량 제한을 다르게 걸어야 했다. DRF의 `BaseThrottle`을 상속해서 직접 구현했는데, 두 가지를 동시에 봐야 했다. API별 윈도우 단위 호출 횟수와, 테넌트 전체의 하루 총 호출 횟수.

카운터는 Redis에 두고 `WATCH`/`MULTI`로 낙관적 동시성 제어를 걸었다.

```python
for _ in range(3):
    try:
        with redis_conn.pipeline() as pipeline:
            pipeline.watch(key_window, key_daily)
            count_window = int(pipeline.get(key_window) or 0)
            count_daily = int(pipeline.get(key_daily) or 0)
            if count_window >= policy.window_limit or count_daily >= policy.daily_limit:
                pipeline.unwatch()
                return False
            pipeline.multi()
            ...
```

같은 테넌트에서 동시에 여러 요청이 들어와도 카운터가 꼬이지 않도록, 조회한 값을 기준으로 갱신을 시도하고 그 사이에 값이 바뀌었으면(`WatchError`) 최대 3번까지 재시도하는 구조로 짰다. 처음엔 이 스로틀링 로직을 만들어두고도 실제로는 아직 제한을 걸지 않았다. 정책 초안만 먼저 짜두고, 실제 제한값 적용은 이후 단계로 미뤘다.

## 남은 생각

고객사용 API는 "지금 필요한 기능"보다 "나중에 바꾸기 힘든 것들"을 먼저 정하는 게 맞는 순서였다. 버전 관리 전략, 인증 방식, 사용량 제한의 뼈대는 한 번 고객사에 노출되면 마음대로 바꾸기 어렵다. 반대로 실제 제한 수치나 개별 엔드포인트 정책은 나중에 조정해도 된다. 이번에 스로틀링 클래스를 먼저 만들고 실제 제한값은 나중으로 미룬 것도 같은 이유였다. 뼈대는 신중하게, 파라미터는 유연하게.
