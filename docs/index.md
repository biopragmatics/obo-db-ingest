---
layout: home
---
The latest export was made on {{ site.data.manifest.date }}.

The following software packages were used:

  {%- for row in site.data.manifest.versions -%}
- {{ row }}
  {%- endfor -%}

<table>
<thead>
  <tr>
    <th>Name</th>
    <th>Terms</th>
    <th>Synonyms</th>
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
    <td>{{ resource[0] }}</td>
    <td>{{ resource[1].summary.terms }}</td>
    <td>{{ resource[1].summary.synonyms }}</td>
    <td><a href="{{ resource[1].obo.iri }}">OBO</a></td>
    <td><a href="{{ resource[1].owl.iri }}">OWL</a></td>
    <td><a href="{{ resource[1].obograph.iri }}">JSON</a></td>
    <td><a href="{{ resource[1].sssom.iri }}">SSSOM</a></td>
    <td><a href="{{ resource[1].nodes.iri }}">Nodes</a></td>
  </tr>
{% endfor %}
</tbody>
</table>
