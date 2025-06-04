---
title: "대형 고객사 하나만을 위한 읽기 전용 DB를 따로 뒀다"
date: 2025-06-05 00:29:00 +0900
categories: [backend, database]
tags: [mysql, django, database-routing, replica]
---

특정 대형 고객사 하나가 우리 서비스 트래픽에서 차지하는 비중이 눈에 띄게 커졌다. 문제는 이 고객사의 조회 패턴이 다른 고객사들과 크게 달랐다는 것. 티켓 리스트, 고객 연관기록, GNB 검색까지 - 무거운 조회가 몰리는 화면에서 유독 이 고객사의 요청이 자주 걸렸고, 공용 읽기 전용 DB의 부하가 다른 고객사에도 영향을 줄 수 있는 상황이었다.

## 왜 레플리카를 늘리는 대신 분리를 택했나

이미 `readonly`, `portal_ro` 두 종류의 읽기 전용 DB가 있었다. 여기에 레플리카를 하나 더 늘려서 부하를 나누는 방법도 있었지만, 그러면 "어떤 요청을 어느 레플리카로 보낼지"를 트래픽 패턴 기준으로 계속 조정해야 한다. 대신 특정 고객사 하나를 위한 전용 읽기 DB를 물리적으로 분리하기로 했다. 이렇게 하면 그 고객사의 조회가 아무리 무거워져도 다른 고객사의 조회 경로에는 영향을 주지 않는다.

Django `DATABASES` 설정에 `client_a_ro`라는 이름으로 별도 DB 커넥션을 추가했다. 같은 데이터베이스, 같은 계정을 쓰지만 호스트만 다른 레플리카를 가리키게 했다.

```python
"client_a_ro": {
    "ENGINE": "django.db.backends.mysql",
    "NAME": env["DB_NAME"],
    "USER": env["DB_USER"],
    "PASSWORD": env["DB_PASSWORD"],
    "HOST": env.get("CLIENT_A_RO_DB_HOST", "DATABASE_HOST"),
    "PORT": env.get("CLIENT_A_RO_DB_PORT", "DATABASE_PORT"),
    ...
}
```

## 라우팅은 일단 하드코딩으로

처음부터 정교한 라우팅 로직을 짜지 않았다. 테스트 단계에서는 해당 고객사의 테넌트 ID를 코드에 직접 박아서, 그 ID로 로그인한 경우에만 `.using("client_a_ro")`를 타도록 분기했다.

```python
if current_tenant_id == CLIENT_A_TENANT_ID:
    qs_ticket_list = (
        Ticket.objects
        .using("client_a_ro")
        .select_related(...)
        .filter(tenant_id=current_tenant_id)
    )
else:
    qs_ticket_list = (
        Ticket.objects
        .using("readonly")
        .select_related(...)
        .filter(tenant_id=current_tenant_id)
    )
```

당연히 이대로 유지할 코드는 아니어서 `TODO` 주석을 남겨뒀다. 티켓 리스트, 고객 연관기록, GNB 검색(티켓/고객) 네 곳에 우선 적용해서 실제 트래픽으로 검증한 뒤, 문제가 없으면 나머지 조회 경로로 넓히는 순서로 갔다.

그 다음 라우팅 로직 자체도 정리했다. 이전에는 레플리카 호스트마다 `try/except`로 환경변수를 개별적으로 읽는 코드가 반복돼 있었는데, 이걸 다른 내부 서비스와 비슷한 패턴으로 맞췄다. 공통 값(`DB_NAME`, `USER`, `PASSWORD`, `PORT` 등)은 변수로 한 번만 선언하고, 레플리카별로 다른 건 호스트 하나뿐이라 `environ.get(..., 기본값)` 형태로 정리해서 설정 파일의 중복을 크게 줄였다.

## 남은 생각

레플리카를 늘리는 것과 레플리카를 분리하는 건 비슷해 보이지만 다른 결정이다. 늘리는 건 부하 분산이 목적이고, 분리는 격리가 목적이다. 대형 고객사 하나의 트래픽 패턴이 통째로 예측 불가능해질 수 있다면, 그 고객사를 위한 자원을 물리적으로 떼어놓는 게 나머지 전체를 지키는 더 확실한 방법이었다. 다만 라우팅 조건을 테넌트 ID 하드코딩으로 시작한 건 명백한 기술 부채였고, 검증이 끝나면 설정 기반으로 바꾸는 작업이 남아있었다.
