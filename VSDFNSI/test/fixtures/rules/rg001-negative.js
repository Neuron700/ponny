// Safe patterns that should not be reported by RG001.
const apiKey = process.env.API_KEY;
const secret = os.environ.get('APP_SECRET');
const token = '${ACCESS_TOKEN}';
const password = 'changeme';
const otherSecret = 'your_api_key_here';
const emptyValue = '';

export { apiKey, secret, token, password, otherSecret, emptyValue };
