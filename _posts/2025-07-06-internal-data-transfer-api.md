---
title: "고객 데이터 이관 API, 느려서 다시 뜯어고친 이야기"
date: 2025-07-06 15:10:00 +0900
categories: [backend]
tags: [django, celery, orm, performance]
---

고객사가 서비스를 떠나거나 브랜드를 통합할 때, 기존 티켓·지식창고 데이터를 다른 테넌트로 옮겨줘야 하는 요청이 종종 들어온다. 이걸 매번 수동으로 처리하던 걸 내부 API로 만들기로 했다. 크게 두 가지였다. 하나는 특정 시점 이전 데이터를 통째로 뽑아주는 추출 API, 다른 하나는 한 브랜드의 데이터를 다른 브랜드로 옮기는 이관 API.

## 추출 API - 접근 제한이 먼저

추출 API는 기존에 있던 관리자 다운로드 로직(`AdminExportView`, `extract_data`)을 참고해서 만들었는데, 민감한 고객 데이터에 접근하는 기능이라 환경변수로 상황에 따라 접근을 제한하도록 처음부터 설계했다. 기능 자체보다 "누가, 언제 이 엔드포인트를 쓸 수 있는가"를 먼저 정하고 코드를 짰다.

## 이관 API - 동기로 짜기엔 무거웠다

이관 API는 처음에 동기 방식으로 짰다가 곧바로 Celery 비동기 태스크로 옮겼다. 브랜드 하나의 티켓, 답변, 라벨, 지식창고 데이터를 전부 복사하는 작업이라 요청-응답 사이클 안에서 끝내기엔 무리였다.

```python
@shared_task(ignore_result=True)
def transfer_data_task(data: dict) -> None:
    view = DataTransferView()
    view.source_tenant_key = data["source_tenant_key"]
    view.source_org_id = data["source_org_id"]
    view.target_tenant_key = data["target_tenant_key"]
    view.target_org_id = data["target_org_id"]
    view.default_user_id = data["default_user_id"]
    view.transfer()
```

문제는 그 다음부터였다. 실제 데이터로 돌려보니 곳곳에서 병목이 나왔다.

## 병목은 대부분 N+1이었다

가장 뼈아팠던 건 고객 매핑 로직이었다. 소스 테넌트의 고객 레코드마다 타겟 테넌트에 같은 고객이 이미 있는지 `Customer.objects.get(...)`으로 매번 조회하고 있었다. 데이터가 몇 건이면 안 보이던 문제가 수천 건 단위로 가니 그대로 N+1이 됐다.

```python
# before: 소스 레코드마다 쿼리 한 번씩
if source_obj.verification_level == "1":
    try:
        target_obj = Customer.objects.get(
            tenant_id=self.target_tenant_id,
            primary_email=source_obj.primary_email,
            verification_level="1",
        )
        ...
    except Customer.DoesNotExist:
        ...
```

이걸 타겟 테넌트의 고객 목록을 한 번에 조회해서 `(verification_level, primary_email)` 또는 `(verification_level, external_id, org_id)`를 키로 하는 dict 캐시로 미리 만들어두는 방식으로 바꿨다. 이후 매핑은 dict 조회 한 번으로 끝난다.

두 번째는 불필요한 필드 로딩이었다. 이관 대상 티켓을 가져올 때 `select_related`는 걸려 있었지만 실제로 쓰지 않는 필드(특히 본문처럼 큰 텍스트 필드)까지 전부 읽어오고 있었다. `.only()`로 실제 사용하는 필드만 지정해서 쿼리당 전송량을 줄였다. 다만 `deepcopy`로 원본 객체를 복사해서 새 레코드를 만드는 메서드에는 `.only()`를 적용할 수 없었다. deferred 필드가 있는 상태로 deepcopy하면 예상치 못하게 동작하기 때문에, 리뷰에서 지적받고 나서 이 부분만 제외했다.

## 남은 생각

이 작업에서 배운 건 "비동기로 옮기면 성능 문제가 해결된다"는 건 착각이라는 것. Celery로 태스크를 옮긴 건 요청 타임아웃 문제를 없앴을 뿐이고, 쿼리 패턴 자체의 비효율은 그대로 남아있었다. 동기든 비동기든 루프 안에서 쿼리를 매번 날리는 코드는 결국 병목이 되고, 그걸 찾아서 캐싱이나 `only()`로 걷어내는 작업은 별개로 필요했다. 그리고 `.only()`처럼 흔히 쓰는 최적화도 `deepcopy`를 쓰는 코드와는 궁합이 안 맞을 수 있다는 걸 이번에 처음 알았다.
