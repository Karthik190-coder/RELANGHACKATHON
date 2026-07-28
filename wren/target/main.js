#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { VM } = require('./vm/vm');

function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.error("Usage: wren <file.wren>");
    process.exit(64);
  }

  const filePath = args[0];
  if (!fs.existsSync(filePath)) {
    console.error(`Could not open file "${filePath}".`);
    process.exit(66);
  }

  let source;
  try {
    source = fs.readFileSync(filePath, 'utf8');
  } catch (err) {
    console.error(`Could not read file "${filePath}": ${err.message}`);
    process.exit(66);
  }

  const vm = new VM();
  vm.cliArgs = args;

  const success = vm.interpret(path.basename(filePath), source);

  if (!success) {
    process.exit(70);
  }
}

main();
