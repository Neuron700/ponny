const output = document.getElementById('output');
output.innerHTML = request.query.html;
output.outerHTML = '<p>' + name + '</p>';
output.insertAdjacentHTML('beforeend', template);
output.innerHTML = '';
