const https = require('https');

const agent = new https.Agent({ rejectUnauthorized: false });
const strict = { strictSSL: false };
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
