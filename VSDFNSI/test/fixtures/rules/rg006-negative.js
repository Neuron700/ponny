const output = document.getElementById('output');
output.textContent = request.query.text;
const label = 'innerHTML';
const helper = { insertAdjacentHTML() {} };
output.innerHTML = '';
