{% rst_l1_header %}
LTS report {{entries.start_date}} to {{entries.stop_date}}
{% end_rst_l1_header %}
This month I used {{ entries.total_delta|dformat('decimal') }} hours on the following tasks:

{% for entry in entries.text_report %}{% rst_l2_header %}
{{entry.project}} / {{ entry.title }}
{% end_rst_l2_header %}
{{ entry.text }}
{% endfor %}
