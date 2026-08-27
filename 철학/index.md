---
layout: default
title: 철학
---
<div class="page-intro">
  <h1 class="visually-hidden">철학</h1>
  <p>철학적 대화. 아래 글들은 AI가 작성했지만 사유는 제가 합니다. 취미 생활입니다.</p>
</div>

{% assign philo_pages = site.pages | where_exp: "p", "p.path contains '철학/'" | where_exp: "p", "p.name != 'index.md'" | sort: "date" | reverse %}
{% assign philo_pinned = philo_pages | where_exp: "p", "p.pin == true" %}
{% assign philo_other = philo_pages | where_exp: "p", "p.pin != true" %}
{% assign philo_pages = philo_pinned | concat: philo_other %}
{% if philo_pages.size > 0 %}
<ul class="post-grid">
  {% for post in philo_pages %}
  <li class="post-card{% if post.pin %} post-card-pinned{% endif %}">
    <a class="post-card-link" href="{{ post.url | relative_url }}">
      <time class="post-list-date" datetime="{{ post.date | date_to_xmlschema }}">
        {% if post.pin %}<span class="pin-badge">📌 고정</span>{% endif %}{{ post.date | date: "%Y년 %-m월 %-d일" }}
      </time>
      <h2 class="post-card-title">{{ post.title }}</h2>
      {% if post.excerpt %}
      <p class="post-card-excerpt">{{ post.excerpt | strip_html | truncatewords: 22 }}</p>
      {% endif %}
    </a>
    {% if post.tags.size > 0 %}
    <div class="post-tags">
      {% for tag in post.tags %}<a class="tag-pill" href="{{ '/tags/' | relative_url }}#{{ tag | slugify }}">{{ tag }}</a>{% endfor %}
    </div>
    {% endif %}
  </li>
  {% endfor %}
</ul>
{% else %}
<p class="empty-state">아직 글이 없습니다.</p>
{% endif %}
