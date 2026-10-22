// eval and exec are mentioned here but not called.
const parsed = JSON.parse('{"a":1}');
const pattern = /a/;
const match = pattern.exec('abc');
const label = 'eval';
const executor = { run() {} };
executor.run();
