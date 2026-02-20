---
title: "켜기만 했던 Datadog RUM을 끈 이유"
date: 2026-02-20 20:27:00 +0900
categories: [infra, backend]
tags: [datadog, apm, cost, monitoring]
---

Datadog을 처음 도입할 때 APM 트레이싱과 함께 브라우저 쪽 RUM(Real User Monitoring)도 같이 켰다. 실사용자의 페이지 로딩, 세션 흐름, 에러를 직접 볼 수 있다는 게 매력적이었다. 그런데 얼마 지나지 않아 이 기능을 다시 껐다. 이유는 단순하다. 비용 문제였다.

## 켤 때는 몰랐던 비용 구조

RUM을 붙일 때 세션 샘플링 비율과 세션 리플레이 샘플링 비율을 둘 다 100%로 설정했다.

```js
window.DD_RUM && window.DD_RUM.init({
  applicationId: "...",
  clientToken: "...",
  site: 'datadoghq.com',
  service: 'web',
  env: 'production',
  version: '1.0.0',
  sessionSampleRate: 100,
  sessionReplaySampleRate: 100,
});
```

RUM은 세션 단위로 과금되는데, 특히 세션 리플레이(사용자의 화면 조작을 그대로 녹화해서 재생할 수 있는 기능)는 일반 세션 수집보다 단가가 훨씬 높다. 도입 초기엔 "일단 다 보이게 켜두자"는 생각으로 100%를 그대로 뒀는데, 트래픽이 쌓이면서 이 값 그대로가 청구서에 고스란히 반영됐다.

## APM은 남기고 RUM만 껐다

정리하면서 백엔드 트레이싱(APM)까지 같이 걷어내는 건 고려하지 않았다. APM은 실제 장애 대응에서 계속 쓰고 있었고, 비용 대비 얻는 정보의 가치가 명확했다. 반면 RUM은 "있으면 좋은" 수준으로 쓰이고 있었고, 실제로 RUM 데이터를 보고 이슈를 해결한 빈도가 그 비용을 정당화할 만큼은 아니었다.

그래서 RUM 관련 코드만 걷어냈다. 설정값(`DATADOG_RUM_APP_ID`, `DATADOG_RUM_TOKEN`)과 템플릿에 박혀 있던 초기화 스크립트를 전부 제거했다.

```diff
- {% if is_production_env %}
-   <script src="https://www.datadoghq-browser-agent.com/us1/v6/datadog-rum.js"></script>
-   <script>
-     window.DD_RUM && window.DD_RUM.init({...});
-     window.DD_RUM && window.DD_RUM.setUser({...});
-   </script>
- {% endif %}
```

베이스 템플릿뿐 아니라 레이아웃에 흩어져 있던 초기화 스크립트까지 찾아서 지워야 했다. 도입할 때는 한 곳에 몰아넣었다고 생각했는데, 이후 레이아웃이 갈라지면서 스크립트도 같이 복제된 흔적이 남아있었다.

## 남은 생각

관측 도구를 들이는 결정은 많이 하지만, 끄는 결정은 상대적으로 잘 안 한다. "일단 켜두면 나중에 쓸모가 있겠지"라는 생각으로 시작했다가, 실제로 얼마나 쓰이는지를 주기적으로 점검하지 않으면 비용만 쌓인다. 이번 건 특히 샘플링 비율을 처음부터 100%로 잡은 게 문제였다. 도입 단계에서는 전수 수집으로 시작하더라도, 어느 정도 지나면 실제로 필요한 샘플링 비율이 얼마인지 다시 판단하고 낮추는 단계가 있어야 했는데 그걸 건너뛰었다. 관측 가능성 도구도 결국 하나의 비용 항목이고, 다른 인프라 자원처럼 정기적으로 "지금도 이 값어치를 하고 있는가"를 물어야 한다는 걸 배웠다.
