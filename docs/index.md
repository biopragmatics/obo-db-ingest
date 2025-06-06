---
layout: home
---

The latest export was made on {{ site.data.manifest.date }}. The following software packages were used:

<ul>
{% for row in site.data.manifest.versions %}
<li>{{ row[0] }} - {{ row[1] }}</li>
{% endfor %}
</ul>

<table class="table table-striped">
<thead>
  <tr>
    <th>Name</th>
    <th>Version</th>
    <th>License</th>
    <th>Terms</th>
    <th>Synonyms</th>
    <th>Mappings</th>
    <th>Relations</th>
    <th>OBO</th>
    <th>OWL</th>
    <th>JSON</th>
    <th>SSSOM</th>
    <th>Nodes</th>
  </tr>
</thead>
<tbody>
{% for resource in site.data.manifest.resources %}
  <tr>
    <td><a href="https://bioregistry.io/{{ resource[0] }}"><code>{{ resource[0] }}</code></a></td>
    <td>{{ resource[1].summary.version }}</td>
    <td>
    {% assign license = resource[1].summary.license %}
    {% if license contains "http" %}
        <a href="{{ license }}">Custom</a>
    {% else %}
        {{ license }}
    {% endif %}
</td>
    <td align="right">{{ resource[1].summary.terms }}</td>
    <td align="right">{{ resource[1].summary.synonyms }}</td>
    <td align="right">{{ resource[1].summary.mappings }}</td>
    <td align="right">{{ resource[1].summary.relations }}</td>
    <td><a href="{{ resource[1].obo.iri }}">OBO</a></td>
    <td><a href="{{ resource[1].owl.iri }}">OWL</a></td>
    <td><a href="{{ resource[1].obograph.iri }}">JSON</a></td>
    <td>{% if resource[1].summary.mappings > 0 %}<a href="{{ resource[1].sssom.iri }}">SSSOM</a>{% endif %}</td>
    <td><a href="{{ resource[1].nodes.iri }}">Nodes</a></td>
  </tr>
{% endfor %}
</tbody>
</table>
