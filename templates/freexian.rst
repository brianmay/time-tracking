{% rst_l1_header %}
LTS report {{entries.start_date}} to {{entries.stop_date}}
{% end_rst_l1_header %}
This time period I used {{ entries.all.total_delta|dformat('decimal') }} hours.

{% for project in entries.projects %}{%rst_l2_header %}
{{ project.name }}
{% end_rst_l2_header %}
For the project {{ project.name }}, I used {{ project.total_delta|dformat('decimal') }} hours in the following tasks:

{% for entry in project.aggregated_text_report %}* {{ entry.title }} ({{ entry.total_delta|dformat('decimal') }} hours)
{% endfor %}
{% for entry in project.aggregated_text_report %}{% if entry.text %}{% rst_l3_header %}
{{ entry.title }}
{% end_rst_l3_header %}
{{ entry.text }}
{% endif %}{% endfor %}
{% endfor %}
