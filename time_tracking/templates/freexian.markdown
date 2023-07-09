# LTS report {{entries.start_date}} to {{entries.stop_date}}

This time period I used {{ entries.all.total_delta|dformat('text') }}.

{% for project in entries.projects %}## {{ project.name }}
For the project {{ project.name }}, I used {{ project.total_delta|dformat('text') }} in the following tasks:

{% for entry in project.aggregated_text_report() %}* {% if entry.task.url %}[{{ entry.task.title }}]({{entry.task.url}}){% else %}{{ entry.task.title }}{% endif %}
{% endfor %}
{% for entry in project.aggregated_text_report() %}{% if entry.text %}### {{ entry.task.title }}
{{ entry.text }}
{% endif %}{% endfor %}
{% endfor %}
