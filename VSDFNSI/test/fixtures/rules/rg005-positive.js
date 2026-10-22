const userInput = "2 + 2";
const result = eval(userInput);
const dynamic = new Function('a', 'return a + 1');
setTimeout("console.log('delayed')", 10);
