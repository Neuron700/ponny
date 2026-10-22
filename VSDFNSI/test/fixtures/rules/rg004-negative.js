const https = require('https');

const agent = new https.Agent({ rejectUnauthorized: true });
const strict = { strictSSL: true };
