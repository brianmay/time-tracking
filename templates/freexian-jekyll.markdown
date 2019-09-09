---
layout: post
title: LTS report {{entries.start_date}} to {{entries.stop_date}}
begin: {{entries.start_date}}
end: {{entries.stop_date}}
hours: {{ entries.all.total_delta|dformat('decimal') }}
---

# LTS report {{entries.start_date}} to {{entries.stop_date}}

This time period I used {{ entries.all.total_delta|dformat('text') }}.

{% for project in entries.projects %}## {{ project.name }}
For the project {{ project.name }}, I used {{ project.total_delta|dformat('text') }} in the following tasks:

{% for entry in project.aggregated_text_report %}* {{ entry.task.name }}
{% endfor %}
{% for entry in project.aggregated_text_report %}{% if entry.text %}### {{ entry.task.name }}
{{ entry.text }}
{% endif %}{% endfor %}
{% endfor %}
