---
title: "매 요청마다 새로 서명하고 있었다 - CloudFront 서명 URL 캐싱"
date: 2026-05-03 10:33:00 +0900
categories: [backend, performance]
tags: [cloudfront, django, cache, performance]
---

첨부파일이나 이미지처럼 민감할 수 있는 미디어는 CloudFront 서명 URL(signed URL)로 서비스하고 있다. 요청마다 만료 시간이 걸린 서명을 새로 생성해서 붙여주는 방식이다. 레거시 서버 레이턴시를 전반적으로 점검하다가, 이 서명 생성 과정이 생각보다 비싼 작업이라는 걸 알게 됐다.

## RSA 서명은 매번 만들 필요가 없다

서명 로직을 보면 매 요청마다 이런 일이 벌어지고 있었다.

```python
def sign_message(message):
    h = SHA256.new(message)
    signer = pkcs1_15.new(settings.SIGNING_PRIVATE_KEY)
    signature = signer.sign(h)
    return signature
```

`pkcs1_15.new(settings.SIGNING_PRIVATE_KEY)`로 서명기(signer) 객체를 매번 새로 만들고 있었다. 이 객체는 private key가 바뀌지 않는 한 매번 다시 만들 이유가 없다. `lru_cache`로 감싸서 프로세스 생명주기 동안 한 번만 생성하도록 바꿨다.

```python
@lru_cache(maxsize=1)
def _get_rsa_signer():
    return pkcs1_15.new(settings.SIGNING_PRIVATE_KEY)


def sign_message(message):
    h = SHA256.new(message)
    return _get_rsa_signer().sign(h)
```

## 서명된 URL 자체도 캐싱했다

여기서 한 단계 더 나갔다. 같은 리소스에 대한 요청이 짧은 시간 안에 반복되는 경우가 많았는데, 그때마다 새 서명을 만들 필요가 있을까 하는 질문이 들었다. 만료 시각을 분 단위로 내림해서 캐시 키로 쓰면, 같은 분 안에 들어온 같은 URL 요청은 서명을 재사용할 수 있다.

```python
@lru_cache(maxsize=2048)
def _cached_presigned_url(url: str, expires_epoch: int):
    expire_date = datetime.datetime.fromtimestamp(expires_epoch, tz=datetime.timezone.utc)
    return _get_cloudfront_signer().generate_presigned_url(url, date_less_than=expire_date)


def get_signed_url(resource_path, should_sign, purpose=None):
    ...
    expire_date = timezone.now() + datetime.timedelta(minutes=expire_minutes)
    expires_epoch = int(expire_date.timestamp())
    expires_epoch = (expires_epoch // 60) * 60  # 같은 분(minute) 단위로 캐시 키를 통일
    return _cached_presigned_url(resource_path, expires_epoch)
```

만료 시각을 분 단위로 내림하면 캐시 키 충돌 범위가 최대 1분으로 제한된다. 서명 URL의 실제 만료 시간(TTL)이 그보다 훨씬 길기 때문에, 이 정도 정밀도 손실은 보안상 문제가 되지 않는다고 판단했다. 대신 같은 분 안에 반복되는 같은 URL 요청은 서명 연산 자체를 건너뛰게 된다.

## 남은 생각

이 최적화의 핵심은 "서명을 캐싱해도 되는가"를 판단하는 기준이 보안 요구사항(짧은 TTL 유지)과 성능 요구사항(반복 서명 비용 절감) 사이에서 타협점을 찾는 문제였다는 것이다. 무작정 캐시 TTL을 늘리면 서명 URL이 오래 유효해져서 보안 목적을 해치고, 반대로 캐싱을 안 하면 매 요청 RSA 서명 비용을 그대로 지불한다. 분 단위 반올림은 두 요구사항이 크게 부딪히지 않는 지점을 찾은 결과였다. 레이턴시 개선 작업을 하다 보면 이런 식으로 "얼마나 정밀해야 하는가"를 다시 따져보는 지점들이 꼭 나온다는 걸 다시 확인했다.
