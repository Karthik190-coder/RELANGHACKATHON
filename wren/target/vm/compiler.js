// Wren Pratt Parser & Bytecode Compiler in JavaScript

const { TokenType, Lexer } = require('./lexer');
const OP = require('./opcodes');
const { ObjFn } = require('./value');

const Precedence = {
  PREC_NONE: 0,
  PREC_LOWEST: 1,
  PREC_ASSIGNMENT: 2,    // =
  PREC_CONDITIONAL: 3,   // ?:
  PREC_LOGICAL_OR: 4,    // ||
  PREC_LOGICAL_AND: 5,   // &&
  PREC_EQUALITY: 6,      // == !=
  PREC_IS: 7,            // is
  PREC_COMPARISON: 8,    // < <= > >=
  PREC_BITWISE_OR: 9,    // |
  PREC_BITWISE_XOR: 10,  // ^
  PREC_BITWISE_AND: 11,  // &
  PREC_BITWISE_SHIFT: 12,// << >>
  PREC_RANGE: 13,        // .. ...
  PREC_TERM: 14,         // + -
  PREC_FACTOR: 15,       // * / %
  PREC_UNARY: 16,        // ! ~ -
  PREC_CALL: 17,         // . [] ()
  PREC_PRIMARY: 18
};

class Compiler {
  constructor(vm, parent = null, isInitializer = false) {
    this.vm = vm;
    this.parent = parent;
    this.fn = new ObjFn();
    this.fn.isInitializer = isInitializer;
    this.isInitializer = isInitializer;
    this.enclosingClass = parent ? parent.enclosingClass : null;

    this.locals = [];
    this.upvalues = [];
    this.scopeDepth = 0;

    this.locals.push({ name: "this", depth: 0, isUpvalue: false });
    this.loop = null;
  }
}

class Parser {
  constructor(vm, moduleName, source) {
    this.vm = vm;
    this.moduleName = moduleName;
    this.lexer = new Lexer(source);

    this.current = null;
    this.previous = null;

    this.compiler = new Compiler(vm);
    this.compiler.fn.module = moduleName;

    this.hadError = false;
    this.panicMode = false;

    this.symbolTable = vm.getOrCreateModule(moduleName);

    this.advance();
  }

  errorAt(token, message) {
    if (this.panicMode) return;
    this.panicMode = true;
    this.hadError = true;

    let msg = `[${this.moduleName} line ${token.line}] Error`;
    if (token.type === TokenType.TOKEN_EOF) {
      msg += " at end";
    } else if (token.type === TokenType.TOKEN_ERROR) {
      // Ignore
    } else {
      msg += ` at '${token.text}'`;
    }
    msg += `: ${message}`;
    console.error(msg);
  }

  error(message) {
    this.errorAt(this.previous, message);
  }

  errorAtCurrent(message) {
    this.errorAt(this.current, message);
  }

  advance() {
    this.previous = this.current;

    for (;;) {
      this.current = this.lexer.scanToken();
      if (this.current.type !== TokenType.TOKEN_ERROR) break;
      this.errorAtCurrent(this.current.text);
    }
  }

  consume(type, message) {
    if (this.current.type === type) {
      this.advance();
      return;
    }
    this.errorAtCurrent(message);
  }

  match(type) {
    if (!this.check(type)) return false;
    this.advance();
    return true;
  }

  check(type) {
    return this.current.type === type;
  }

  ignoreNewlines() {
    while (this.check(TokenType.TOKEN_LINE)) {
      this.advance();
    }
  }

  emitByte(byte) {
    this.compiler.fn.code.push(byte);
  }

  emitBytes(b1, b2) {
    this.emitByte(b1);
    this.emitByte(b2);
  }

  emitShort(value) {
    this.emitByte(value & 0xff);
    this.emitByte((value >> 8) & 0xff);
  }

  emitOp(op) {
    this.emitByte(op);
  }

  emitConstant(value) {
    const constantIndex = this.addConstant(value);
    this.emitBytes(OP.CONSTANT, constantIndex);
  }

  addConstant(value) {
    const constants = this.compiler.fn.constants;
    for (let i = 0; i < constants.length; i++) {
      if (constants[i] === value) return i;
    }
    constants.push(value);
    return constants.length - 1;
  }

  emitJump(instruction) {
    this.emitByte(instruction);
    this.emitByte(0xff);
    this.emitByte(0xff);
    return this.compiler.fn.code.length - 2;
  }

  patchJump(offset) {
    const jump = this.compiler.fn.code.length - offset - 2;
    this.compiler.fn.code[offset] = jump & 0xff;
    this.compiler.fn.code[offset + 1] = (jump >> 8) & 0xff;
  }

  emitLoop(loopStart) {
    this.emitByte(OP.LOOP);
    const offset = this.compiler.fn.code.length - loopStart + 2;
    this.emitByte(offset & 0xff);
    this.emitByte((offset >> 8) & 0xff);
  }

  emitReturn() {
    if (this.compiler.isInitializer) {
      this.emitOp(OP.LOAD_LOCAL_0);
    } else {
      this.emitOp(OP.NULL);
    }
    this.emitOp(OP.RETURN);
  }

  declareVariable(nameToken) {
    if (this.compiler.scopeDepth === 0) {
      return this.vm.defineModuleVar(this.moduleName, nameToken.text, null);
    }

    for (let i = this.compiler.locals.length - 1; i >= 0; i--) {
      const local = this.compiler.locals[i];
      if (local.depth !== -1 && local.depth < this.compiler.scopeDepth) break;
      if (local.name === nameToken.text) {
        this.error(`Variable '${nameToken.text}' already declared in this scope.`);
      }
    }

    this.compiler.locals.push({
      name: nameToken.text,
      depth: -1,
      isUpvalue: false
    });
    return this.compiler.locals.length - 1;
  }

  defineVariable(varIndex) {
    if (this.compiler.scopeDepth === 0) {
      this.emitBytes(OP.STORE_MODULE_VAR, varIndex);
      this.emitOp(OP.POP);
    } else {
      this.compiler.locals[this.compiler.locals.length - 1].depth = this.compiler.scopeDepth;
    }
  }

  resolveLocal(compiler, name) {
    for (let i = compiler.locals.length - 1; i >= 0; i--) {
      const local = compiler.locals[i];
      if (local.name === name) {
        return i;
      }
    }
    return -1;
  }

  addUpvalue(compiler, index, isLocal) {
    for (let i = 0; i < compiler.upvalues.length; i++) {
      const upvalue = compiler.upvalues[i];
      if (upvalue.index === index && upvalue.isLocal === isLocal) {
        return i;
      }
    }

    compiler.upvalues.push({ isLocal, index });
    compiler.fn.numUpvalues = compiler.upvalues.length;
    return compiler.upvalues.length - 1;
  }

  resolveUpvalue(compiler, name) {
    if (compiler.parent === null) return -1;

    const local = this.resolveLocal(compiler.parent, name);
    if (local !== -1) {
      compiler.parent.locals[local].isUpvalue = true;
      return this.addUpvalue(compiler, local, true);
    }

    const upvalue = this.resolveUpvalue(compiler.parent, name);
    if (upvalue !== -1) {
      return this.addUpvalue(compiler, upvalue, false);
    }

    return -1;
  }

  parse() {
    this.ignoreNewlines();
    while (!this.match(TokenType.TOKEN_EOF)) {
      this.definition();
      this.ignoreNewlines();
    }
    this.emitOp(OP.END_MODULE);
    this.emitOp(OP.RETURN);
    return this.hadError ? null : this.compiler.fn;
  }

  definition() {
    if (this.match(TokenType.TOKEN_CLASS)) {
      this.classDeclaration();
    } else if (this.match(TokenType.TOKEN_FOREIGN)) {
      if (this.match(TokenType.TOKEN_CLASS)) {
        this.classDeclaration(true);
      } else {
        this.error("Expect 'class' after 'foreign'.");
      }
    } else if (this.match(TokenType.TOKEN_VAR)) {
      this.varDeclaration();
    } else if (this.match(TokenType.TOKEN_IMPORT)) {
      this.importStatement();
    } else {
      this.statement();
    }
  }

  varDeclaration() {
    this.consume(TokenType.TOKEN_NAME, "Expect variable name.");
    const nameToken = this.previous;
    const varIndex = this.declareVariable(nameToken);

    if (this.match(TokenType.TOKEN_EQUAL)) {
      this.expression();
    } else {
      this.emitOp(OP.NULL);
    }

    this.defineVariable(varIndex);
  }

  classDeclaration(isForeign = false) {
    this.consume(TokenType.TOKEN_NAME, "Expect class name.");
    const classNameToken = this.previous;
    const nameStringIndex = this.addConstant(classNameToken.text);

    this.emitConstant(classNameToken.text);

    if (this.match(TokenType.TOKEN_IS)) {
      this.expression();
    } else {
      this.emitConstant("Object");
      const objSymbol = this.vm.findModuleVar(this.moduleName, "Object");
      if (objSymbol !== -1) {
        this.emitBytes(OP.LOAD_MODULE_VAR, objSymbol);
      } else {
        this.emitConstant("Object");
      }
    }

    if (isForeign) {
      this.emitBytes(OP.FOREIGN_CLASS, nameStringIndex);
    } else {
      this.emitBytes(OP.CLASS, nameStringIndex);
    }

    const varIndex = this.declareVariable(classNameToken);
    this.defineVariable(varIndex);

    const enclosingClass = {
      nameToken: classNameToken,
      name: classNameToken.text,
      fields: new Map(),
      isForeign
    };

    const previousCompilerClass = this.compiler.enclosingClass;
    this.compiler.enclosingClass = enclosingClass;

    this.consume(TokenType.TOKEN_LEFT_BRACE, "Expect '{' before class body.");
    this.ignoreNewlines();

    while (!this.check(TokenType.TOKEN_RIGHT_BRACE) && !this.check(TokenType.TOKEN_EOF)) {
      this.method(classNameToken);
      this.ignoreNewlines();
    }

    this.consume(TokenType.TOKEN_RIGHT_BRACE, "Expect '}' after class body.");
    this.emitOp(OP.END_CLASS);

    this.compiler.enclosingClass = previousCompilerClass;
  }

  method(classNameToken) {
    let isForeign = false;
    let isStatic = false;
    let isConstruct = false;

    if (this.match(TokenType.TOKEN_FOREIGN)) isForeign = true;
    if (this.match(TokenType.TOKEN_STATIC)) isStatic = true;
    if (this.match(TokenType.TOKEN_CONSTRUCT)) isConstruct = true;

    let methodSymbol;
    let symbolIndex;

    if (isForeign) {
      methodSymbol = this.methodSignature();
      symbolIndex = this.vm.ensureSymbol(methodSymbol);
      this.emitConstant(methodSymbol);
    } else {
      // Parameters belong to the method compiler, not the surrounding class
      // compiler. Declaring them before switching compilers caused methods
      // and constructors to lose their parameter bindings in their bodies.
      const methodCompiler = new Compiler(this.vm, this.compiler, isConstruct);
      const prevCompiler = this.compiler;
      this.compiler = methodCompiler;
      this.beginScope();
      methodSymbol = this.methodSignature();
      symbolIndex = this.vm.ensureSymbol(methodSymbol);
      methodCompiler.fn.name = methodSymbol;
      this.consume(TokenType.TOKEN_LEFT_BRACE, "Expect '{' before method body.");
      this.block();
      this.emitReturn();
      const fn = this.endCompiler();
      this.compiler = prevCompiler;

      this.emitClosure(fn);
    }

    this.namedVariable(classNameToken, false);

    if (isConstruct || isStatic) {
      this.emitByte(OP.METHOD_STATIC);
      this.emitShort(symbolIndex);
    } else {
      this.emitByte(OP.METHOD_INSTANCE);
      this.emitShort(symbolIndex);
    }
  }

  methodSignature() {
    let name = "";
    if (this.match(TokenType.TOKEN_NAME)) {
      name = this.previous.text;
    } else if (this.match(TokenType.TOKEN_PLUS)) name = "+";
    else if (this.match(TokenType.TOKEN_MINUS)) name = "-";
    else if (this.match(TokenType.TOKEN_STAR)) name = "*";
    else if (this.match(TokenType.TOKEN_SLASH)) name = "/";
    else if (this.match(TokenType.TOKEN_PERCENT)) name = "%";
    else if (this.match(TokenType.TOKEN_LESS)) name = "<";
    else if (this.match(TokenType.TOKEN_GREATER)) name = ">";
    else if (this.match(TokenType.TOKEN_EQUALEQUAL)) name = "==";
    else if (this.match(TokenType.TOKEN_BANGEQUAL)) name = "!=";
    else if (this.match(TokenType.TOKEN_LEFT_BRACKET)) {
      this.consume(TokenType.TOKEN_RIGHT_BRACKET, "Expect ']' after '['.");
      name = "[]";
      if (this.match(TokenType.TOKEN_EQUAL)) name = "[]=";
    } else {
      this.errorAtCurrent("Expect method name.");
    }

    let arity = 0;
    if (this.match(TokenType.TOKEN_LEFT_PAREN)) {
      if (!this.check(TokenType.TOKEN_RIGHT_PAREN)) {
        do {
          this.consume(TokenType.TOKEN_NAME, "Expect parameter name.");
          this.declareVariable(this.previous);
          this.defineVariable(this.compiler.locals.length - 1);
          arity++;
        } while (this.match(TokenType.TOKEN_COMMA));
      }
      this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after parameters.");
      return `${name}(${arity})`;
    }

    if (this.match(TokenType.TOKEN_EQUAL)) {
      this.consume(TokenType.TOKEN_LEFT_PAREN, "Expect '(' after '=' in setter.");
      this.consume(TokenType.TOKEN_NAME, "Expect parameter name.");
      this.declareVariable(this.previous);
      this.defineVariable(this.compiler.locals.length - 1);
      this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after setter parameter.");
      return `${name}=(_)`;
    }

    return name;
  }

  importStatement() {
    this.consume(TokenType.TOKEN_STRING, "Expect module path string.");
    const moduleName = this.previous.value;
    const moduleIndex = this.addConstant(moduleName);

    this.emitBytes(OP.IMPORT_MODULE, moduleIndex);

    if (this.match(TokenType.TOKEN_FOR)) {
      do {
        this.consume(TokenType.TOKEN_NAME, "Expect variable name to import.");
        const varName = this.previous.text;
        const varStringIndex = this.addConstant(varName);
        this.emitBytes(OP.IMPORT_VARIABLE, varStringIndex);

        const localIndex = this.declareVariable(this.previous);
        this.defineVariable(localIndex);
      } while (this.match(TokenType.TOKEN_COMMA));
    } else {
      this.emitOp(OP.POP);
    }
  }

  statement() {
    if (this.match(TokenType.TOKEN_IF)) {
      this.ifStatement();
    } else if (this.match(TokenType.TOKEN_WHILE)) {
      this.whileStatement();
    } else if (this.match(TokenType.TOKEN_FOR)) {
      this.forStatement();
    } else if (this.match(TokenType.TOKEN_RETURN)) {
      this.returnStatement();
    } else if (this.match(TokenType.TOKEN_BREAK)) {
      this.breakStatement();
    } else if (this.match(TokenType.TOKEN_CONTINUE)) {
      this.continueStatement();
    } else if (this.match(TokenType.TOKEN_LEFT_BRACE)) {
      this.beginScope();
      this.block();
      this.endScope();
    } else {
      this.expressionStatement();
    }
  }

  expressionStatement() {
    this.expression();
    this.emitOp(OP.POP);
  }

  ifStatement() {
    this.consume(TokenType.TOKEN_LEFT_PAREN, "Expect '(' after 'if'.");
    this.expression();
    this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after condition.");

    const thenJump = this.emitJump(OP.JUMP_IF);

    this.statement();

    if (this.match(TokenType.TOKEN_ELSE)) {
      const elseJump = this.emitJump(OP.JUMP);
      this.patchJump(thenJump);
      this.statement();
      this.patchJump(elseJump);
    } else {
      this.patchJump(thenJump);
    }
  }

  whileStatement() {
    const loopStart = this.compiler.fn.code.length;
    this.consume(TokenType.TOKEN_LEFT_PAREN, "Expect '(' after 'while'.");
    this.expression();
    this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after condition.");

    const exitJump = this.emitJump(OP.JUMP_IF);

    const prevLoop = this.compiler.loop;
    this.compiler.loop = { start: loopStart, exitJumps: [exitJump] };

    this.statement();
    this.emitLoop(loopStart);

    this.compiler.loop.exitJumps.forEach(j => this.patchJump(j));
    this.compiler.loop = prevLoop;
  }

  forStatement() {
    this.beginScope();
    this.consume(TokenType.TOKEN_LEFT_PAREN, "Expect '(' after 'for'.");
    this.consume(TokenType.TOKEN_NAME, "Expect variable name in for loop.");
    const varNameToken = this.previous;

    this.consume(TokenType.TOKEN_IN, "Expect 'in' after for loop variable.");
    this.expression();
    this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after sequence.");

    const seqLocal = this.declareVariable({ text: "seq" });
    this.defineVariable(seqLocal);

    this.emitOp(OP.NULL);
    const iterLocal = this.declareVariable({ text: "iter" });
    this.defineVariable(iterLocal);

    const loopStart = this.compiler.fn.code.length;

    this.emitBytes(OP.LOAD_LOCAL, seqLocal);
    this.emitBytes(OP.LOAD_LOCAL, iterLocal);
    const iterateSym = this.vm.ensureSymbol("iterate(1)");
    this.emitBytes(OP.CALL_1, iterateSym);

    this.emitBytes(OP.STORE_LOCAL, iterLocal);

    const exitJump = this.emitJump(OP.JUMP_IF);

    this.beginScope();
    this.emitBytes(OP.LOAD_LOCAL, seqLocal);
    this.emitBytes(OP.LOAD_LOCAL, iterLocal);
    const valueSym = this.vm.ensureSymbol("iteratorValue(1)");
    this.emitBytes(OP.CALL_1, valueSym);

    const userVar = this.declareVariable(varNameToken);
    this.defineVariable(userVar);

    const prevLoop = this.compiler.loop;
    this.compiler.loop = { start: loopStart, exitJumps: [exitJump] };

    this.statement();

    this.endScope();
    this.emitLoop(loopStart);

    this.compiler.loop.exitJumps.forEach(j => this.patchJump(j));
    this.compiler.loop = prevLoop;
    this.endScope();
  }

  returnStatement() {
    if (this.check(TokenType.TOKEN_LINE) || this.check(TokenType.TOKEN_RIGHT_BRACE)) {
      this.emitReturn();
    } else {
      this.expression();
      this.emitOp(OP.RETURN);
    }
  }

  breakStatement() {
    if (!this.compiler.loop) {
      this.error("Cannot use 'break' outside of a loop.");
      return;
    }
    const jump = this.emitJump(OP.JUMP);
    this.compiler.loop.exitJumps.push(jump);
  }

  continueStatement() {
    if (!this.compiler.loop) {
      this.error("Cannot use 'continue' outside of a loop.");
      return;
    }
    this.emitLoop(this.compiler.loop.start);
  }

  block() {
    this.ignoreNewlines();
    while (!this.check(TokenType.TOKEN_RIGHT_BRACE) && !this.check(TokenType.TOKEN_EOF)) {
      this.definition();
      this.ignoreNewlines();
    }
    this.consume(TokenType.TOKEN_RIGHT_BRACE, "Expect '}' after block.");
  }

  expression() {
    this.parsePrecedence(Precedence.PREC_ASSIGNMENT);
  }

  parsePrecedence(precedence) {
    this.advance();
    const prefixRule = this.getRule(this.previous.type).prefix;
    if (!prefixRule) {
      this.error("Expect expression.");
      return;
    }

    const canAssign = precedence <= Precedence.PREC_ASSIGNMENT;
    prefixRule.call(this, canAssign);

    while (precedence <= this.getRule(this.current.type).precedence) {
      this.advance();
      const infixRule = this.getRule(this.previous.type).infix;
      infixRule.call(this, canAssign);
    }

    if (canAssign && this.match(TokenType.TOKEN_EQUAL)) {
      this.error("Invalid assignment target.");
    }
  }

  getRule(type) {
    return RULES[type] || { prefix: null, infix: null, precedence: Precedence.PREC_NONE };
  }

  number(canAssign) {
    this.emitConstant(this.previous.value);
  }

  string(canAssign) {
    this.emitConstant(this.previous.value);
  }

  stringInterpolation(canAssign) {
    this.emitConstant("List");
    const listSym = this.vm.findModuleVar(this.moduleName, "List");
    if (listSym !== -1) {
      this.emitBytes(OP.LOAD_MODULE_VAR, listSym);
    }
    const newSym = this.vm.ensureSymbol("new()");
    this.emitBytes(OP.CALL_0, newSym);

    do {
      this.emitConstant(this.previous.value);
      const addSym = this.vm.ensureSymbol("add(1)");
      this.emitBytes(OP.CALL_1, addSym);
      this.emitOp(OP.POP);

      this.ignoreNewlines();
      this.expression();
      this.emitBytes(OP.CALL_1, addSym);
      this.emitOp(OP.POP);

      this.ignoreNewlines();
    } while (this.match(TokenType.TOKEN_INTERPOLATION));

    this.consume(TokenType.TOKEN_STRING, "Expect end of string interpolation.");
    this.emitConstant(this.previous.value);
    const addSym = this.vm.ensureSymbol("add(1)");
    this.emitBytes(OP.CALL_1, addSym);
    this.emitOp(OP.POP);

    const joinSym = this.vm.ensureSymbol("join()");
    this.emitBytes(OP.CALL_0, joinSym);
  }

  literal(canAssign) {
    switch (this.previous.type) {
      case TokenType.TOKEN_FALSE: this.emitOp(OP.FALSE); break;
      case TokenType.TOKEN_TRUE: this.emitOp(OP.TRUE); break;
      case TokenType.TOKEN_NULL: this.emitOp(OP.NULL); break;
    }
  }

  this_(canAssign) {
    this.emitBytes(OP.LOAD_LOCAL_0);
  }

  super_(canAssign) {
    this.emitBytes(OP.LOAD_LOCAL_0);
  }

  unaryOp(canAssign) {
    const operatorType = this.previous.type;
    this.parsePrecedence(Precedence.PREC_UNARY + 1);

    let methodSymbol = "";
    switch (operatorType) {
      case TokenType.TOKEN_BANG: methodSymbol = "!(0)"; break;
      case TokenType.TOKEN_TILDE: methodSymbol = "~(0)"; break;
      case TokenType.TOKEN_MINUS: methodSymbol = "-(0)"; break;
    }

    const symIndex = this.vm.ensureSymbol(methodSymbol);
    this.emitBytes(OP.CALL_0, symIndex);
  }

  variable(canAssign) {
    this.namedVariable(this.previous, canAssign);
    if (canAssign) {
      this.callInfix(canAssign);
    }
  }

  namedVariable(nameToken, canAssign) {
    let getOp, setOp, arg;
    let local = this.resolveLocal(this.compiler, nameToken.text);

    if (local !== -1) {
      getOp = OP.LOAD_LOCAL;
      setOp = OP.STORE_LOCAL;
      arg = local;
    } else {
      let upvalue = this.resolveUpvalue(this.compiler, nameToken.text);
      if (upvalue !== -1) {
        getOp = OP.LOAD_UPVALUE;
        setOp = OP.STORE_UPVALUE;
        arg = upvalue;
      } else {
        let symbol = this.vm.findModuleVar(this.moduleName, nameToken.text);
        if (symbol === -1) {
          symbol = this.vm.defineModuleVar(this.moduleName, nameToken.text, null);
        }
        getOp = OP.LOAD_MODULE_VAR;
        setOp = OP.STORE_MODULE_VAR;
        arg = symbol;
      }
    }

    if (canAssign && this.match(TokenType.TOKEN_EQUAL)) {
      this.expression();
      this.emitBytes(setOp, arg);
    } else {
      this.emitBytes(getOp, arg);
    }
  }

  callInfix(canAssign) {
    let arity = 0;
    if (this.match(TokenType.TOKEN_LEFT_PAREN)) {
      if (!this.check(TokenType.TOKEN_RIGHT_PAREN)) {
        do {
          this.expression();
          arity++;
        } while (this.match(TokenType.TOKEN_COMMA));
      }
      this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after arguments.");
      const callOp = OP[`CALL_${arity}`];
      const symIndex = this.vm.ensureSymbol(`call(${arity})`);
      this.emitBytes(callOp, symIndex);
    } else if (this.match(TokenType.TOKEN_LEFT_BRACE)) {
      const fnCompiler = new Compiler(this.vm, this.compiler);
      const prevCompiler = this.compiler;
      this.compiler = fnCompiler;

      let blockArity = 0;
      this.beginScope();
      if (this.match(TokenType.TOKEN_PIPE)) {
        if (!this.check(TokenType.TOKEN_PIPE)) {
          do {
            this.consume(TokenType.TOKEN_NAME, "Expect parameter name.");
            this.declareVariable(this.previous);
            this.defineVariable(this.compiler.locals.length - 1);
            blockArity++;
          } while (this.match(TokenType.TOKEN_COMMA));
        }
        this.consume(TokenType.TOKEN_PIPE, "Expect '|' after function parameters.");
      }

      this.compiler.fn.arity = blockArity;
      this.block();
      this.emitReturn();
      const fn = this.endCompiler();
      this.compiler = prevCompiler;

      this.emitClosure(fn);
      const symIndex = this.vm.ensureSymbol(`call(1)`);
      this.emitBytes(OP.CALL_1, symIndex);
    }
  }

  field(canAssign) {
    const fieldName = this.previous.text;
    let fieldIndex = 0;
    if (this.compiler.enclosingClass) {
      if (!this.compiler.enclosingClass.fields.has(fieldName)) {
        fieldIndex = this.compiler.enclosingClass.fields.size;
        this.compiler.enclosingClass.fields.set(fieldName, fieldIndex);
      } else {
        fieldIndex = this.compiler.enclosingClass.fields.get(fieldName);
      }
    }

    if (canAssign && this.match(TokenType.TOKEN_EQUAL)) {
      this.expression();
      this.emitBytes(OP.STORE_FIELD_THIS, fieldIndex);
    } else {
      this.emitBytes(OP.LOAD_FIELD_THIS, fieldIndex);
    }
  }

  and_(canAssign) {
    this.ignoreNewlines();
    const jump = this.emitJump(OP.AND);
    this.parsePrecedence(Precedence.PREC_LOGICAL_AND);
    this.patchJump(jump);
  }

  or_(canAssign) {
    this.ignoreNewlines();
    const jump = this.emitJump(OP.OR);
    this.parsePrecedence(Precedence.PREC_LOGICAL_OR);
    this.patchJump(jump);
  }

  conditional(canAssign) {
    this.ignoreNewlines();
    const ifJump = this.emitJump(OP.JUMP_IF);
    this.expression();
    this.consume(TokenType.TOKEN_COLON, "Expect ':' in ternary conditional.");
    const elseJump = this.emitJump(OP.JUMP);
    this.patchJump(ifJump);
    this.expression();
    this.patchJump(elseJump);
  }

  binary(canAssign) {
    const operatorType = this.previous.type;
    const rule = this.getRule(operatorType);

    this.parsePrecedence(rule.precedence + 1);

    let methodSymbol = "";
    switch (operatorType) {
      case TokenType.TOKEN_PLUS: methodSymbol = "+(1)"; break;
      case TokenType.TOKEN_MINUS: methodSymbol = "-(1)"; break;
      case TokenType.TOKEN_STAR: methodSymbol = "*(1)"; break;
      case TokenType.TOKEN_SLASH: methodSymbol = "/(1)"; break;
      case TokenType.TOKEN_PERCENT: methodSymbol = "%(1)"; break;
      case TokenType.TOKEN_LESS: methodSymbol = "<(1)"; break;
      case TokenType.TOKEN_LESSEQUAL: methodSymbol = "<=(1)"; break;
      case TokenType.TOKEN_GREATER: methodSymbol = ">(1)"; break;
      case TokenType.TOKEN_GREATEREQUAL: methodSymbol = ">=(1)"; break;
      case TokenType.TOKEN_EQUALEQUAL: methodSymbol = "==(1)"; break;
      case TokenType.TOKEN_BANGEQUAL: methodSymbol = "!=(1)"; break;
      case TokenType.TOKEN_PIPE: methodSymbol = "|(1)"; break;
      case TokenType.TOKEN_AMP: methodSymbol = "&(1)"; break;
      case TokenType.TOKEN_CARET: methodSymbol = "^(1)"; break;
      case TokenType.TOKEN_SHL: methodSymbol = "<<(1)"; break;
      case TokenType.TOKEN_SHR: methodSymbol = ">>(1)"; break;
      case TokenType.TOKEN_DOTDOT: methodSymbol = "..(1)"; break;
      case TokenType.TOKEN_DOTDOTDOT: methodSymbol = "...(1)"; break;
      case TokenType.TOKEN_IS: methodSymbol = "is(1)"; break;
    }

    const symIndex = this.vm.ensureSymbol(methodSymbol);
    this.emitBytes(OP.CALL_1, symIndex);
  }

  dot(canAssign) {
    this.consume(TokenType.TOKEN_NAME, "Expect method name after '.'.");
    const name = this.previous.text;

    let arity = 0;
    if (this.match(TokenType.TOKEN_LEFT_PAREN)) {
      if (!this.check(TokenType.TOKEN_RIGHT_PAREN)) {
        do {
          this.expression();
          arity++;
        } while (this.match(TokenType.TOKEN_COMMA));
      }
      this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after arguments.");
      const symIndex = this.vm.ensureSymbol(`${name}(${arity})`);
      const callOp = OP[`CALL_${arity}`];
      this.emitBytes(callOp, symIndex);
    } else if (this.match(TokenType.TOKEN_LEFT_BRACE)) {
      const fnCompiler = new Compiler(this.vm, this.compiler);
      const prevCompiler = this.compiler;
      this.compiler = fnCompiler;

      let blockArity = 0;
      this.beginScope();
      if (this.match(TokenType.TOKEN_PIPE)) {
        if (!this.check(TokenType.TOKEN_PIPE)) {
          do {
            this.consume(TokenType.TOKEN_NAME, "Expect parameter name.");
            this.declareVariable(this.previous);
            this.defineVariable(this.compiler.locals.length - 1);
            blockArity++;
          } while (this.match(TokenType.TOKEN_COMMA));
        }
        this.consume(TokenType.TOKEN_PIPE, "Expect '|' after function parameters.");
      }

      this.compiler.fn.arity = blockArity;
      this.block();
      this.emitReturn();
      const fn = this.endCompiler();
      this.compiler = prevCompiler;

      this.emitClosure(fn);
      const symIndex = this.vm.ensureSymbol(`${name}(1)`);
      this.emitBytes(OP.CALL_1, symIndex);
    } else if (canAssign && this.match(TokenType.TOKEN_EQUAL)) {
      this.expression();
      const symIndex = this.vm.ensureSymbol(`${name}=(_)`);
      this.emitBytes(OP.CALL_1, symIndex);
    } else {
      const symIndex = this.vm.ensureSymbol(name);
      this.emitBytes(OP.CALL_0, symIndex);
    }
  }

  subscript(canAssign) {
    let arity = 0;
    if (!this.check(TokenType.TOKEN_RIGHT_BRACKET)) {
      do {
        this.expression();
        arity++;
      } while (this.match(TokenType.TOKEN_COMMA));
    }
    this.consume(TokenType.TOKEN_RIGHT_BRACKET, "Expect ']' after subscript arguments.");

    if (canAssign && this.match(TokenType.TOKEN_EQUAL)) {
      this.expression();
      arity++;
      const symIndex = this.vm.ensureSymbol(`[]=(${arity})`);
      const callOp = OP[`CALL_${arity}`];
      this.emitBytes(callOp, symIndex);
    } else {
      const symIndex = this.vm.ensureSymbol(`[](${arity})`);
      const callOp = OP[`CALL_${arity}`];
      this.emitBytes(callOp, symIndex);
    }
  }

  grouping(canAssign) {
    this.expression();
    this.consume(TokenType.TOKEN_RIGHT_PAREN, "Expect ')' after expression.");
  }

  listLiteral(canAssign) {
    this.emitConstant("List");
    const listSym = this.vm.findModuleVar(this.moduleName, "List");
    if (listSym !== -1) {
      this.emitBytes(OP.LOAD_MODULE_VAR, listSym);
    }

    const newSym = this.vm.ensureSymbol("new()");
    this.emitBytes(OP.CALL_0, newSym);

    this.ignoreNewlines();
    if (!this.check(TokenType.TOKEN_RIGHT_BRACKET)) {
      do {
        this.ignoreNewlines();
        if (this.check(TokenType.TOKEN_RIGHT_BRACKET)) break;

        this.expression();

        const addSym = this.vm.ensureSymbol("add(1)");
        this.emitBytes(OP.CALL_1, addSym);
        this.emitOp(OP.POP);
      } while (this.match(TokenType.TOKEN_COMMA));
    }

    this.ignoreNewlines();
    this.consume(TokenType.TOKEN_RIGHT_BRACKET, "Expect ']' after list elements.");
  }

  mapLiteral(canAssign) {
    const mapSym = this.vm.findModuleVar(this.moduleName, "Map");
    if (mapSym !== -1) {
      this.emitBytes(OP.LOAD_MODULE_VAR, mapSym);
    }

    const newSym = this.vm.ensureSymbol("new()");
    this.emitBytes(OP.CALL_0, newSym);

    this.ignoreNewlines();
    if (!this.check(TokenType.TOKEN_RIGHT_BRACE)) {
      do {
        this.ignoreNewlines();
        if (this.check(TokenType.TOKEN_RIGHT_BRACE)) break;

        this.expression();
        this.consume(TokenType.TOKEN_COLON, "Expect ':' after map key.");
        this.expression();

        const addSym = this.vm.ensureSymbol("addCore(2)");
        this.emitBytes(OP.CALL_2, addSym);
        this.emitOp(OP.POP);
      } while (this.match(TokenType.TOKEN_COMMA));
    }

    this.ignoreNewlines();
    this.consume(TokenType.TOKEN_RIGHT_BRACE, "Expect '}' after map entries.");
  }

  beginScope() {
    this.compiler.scopeDepth++;
  }

  endScope() {
    this.compiler.scopeDepth--;
    while (
      this.compiler.locals.length > 0 &&
      this.compiler.locals[this.compiler.locals.length - 1].depth > this.compiler.scopeDepth
    ) {
      const local = this.compiler.locals.pop();
      if (local.isUpvalue) {
        this.emitOp(OP.CLOSE_UPVALUE);
      } else {
        this.emitOp(OP.POP);
      }
    }
  }

  endCompiler() {
    return this.compiler.fn;
  }

  emitClosure(fn) {
    const constantIndex = this.addConstant(fn);
    this.emitBytes(OP.CLOSURE, constantIndex);

    for (let i = 0; i < this.compiler.upvalues.length; i++) {
      const upvalue = this.compiler.upvalues[i];
      this.emitByte(upvalue.isLocal ? 1 : 0);
      this.emitByte(upvalue.index);
    }
  }
}

const RULES = {};

function defineRule(type, prefix, infix, precedence) {
  RULES[type] = { prefix, infix, precedence };
}

defineRule(TokenType.TOKEN_LEFT_PAREN, Parser.prototype.grouping, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_DOT, null, Parser.prototype.dot, Precedence.PREC_CALL);
defineRule(TokenType.TOKEN_LEFT_BRACKET, Parser.prototype.listLiteral, Parser.prototype.subscript, Precedence.PREC_CALL);
defineRule(TokenType.TOKEN_LEFT_BRACE, Parser.prototype.mapLiteral, null, Precedence.PREC_NONE);

defineRule(TokenType.TOKEN_THIS, Parser.prototype.this_, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_SUPER, Parser.prototype.super_, null, Precedence.PREC_NONE);

defineRule(TokenType.TOKEN_BANG, Parser.prototype.unaryOp, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_TILDE, Parser.prototype.unaryOp, null, Precedence.PREC_NONE);

defineRule(TokenType.TOKEN_NUMBER, Parser.prototype.number, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_STRING, Parser.prototype.string, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_INTERPOLATION, Parser.prototype.stringInterpolation, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_FALSE, Parser.prototype.literal, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_TRUE, Parser.prototype.literal, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_NULL, Parser.prototype.literal, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_NAME, Parser.prototype.variable, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_FIELD, Parser.prototype.field, null, Precedence.PREC_NONE);
defineRule(TokenType.TOKEN_STATIC_FIELD, Parser.prototype.field, null, Precedence.PREC_NONE);

defineRule(TokenType.TOKEN_PIPEPIPE, null, Parser.prototype.or_, Precedence.PREC_LOGICAL_OR);
defineRule(TokenType.TOKEN_AMPAMP, null, Parser.prototype.and_, Precedence.PREC_LOGICAL_AND);
defineRule(TokenType.TOKEN_QUESTION, null, Parser.prototype.conditional, Precedence.PREC_CONDITIONAL);

defineRule(TokenType.TOKEN_PLUS, null, Parser.prototype.binary, Precedence.PREC_TERM);
defineRule(TokenType.TOKEN_MINUS, Parser.prototype.unaryOp, Parser.prototype.binary, Precedence.PREC_TERM);
defineRule(TokenType.TOKEN_STAR, null, Parser.prototype.binary, Precedence.PREC_FACTOR);
defineRule(TokenType.TOKEN_SLASH, null, Parser.prototype.binary, Precedence.PREC_FACTOR);
defineRule(TokenType.TOKEN_PERCENT, null, Parser.prototype.binary, Precedence.PREC_FACTOR);

defineRule(TokenType.TOKEN_EQUALEQUAL, null, Parser.prototype.binary, Precedence.PREC_EQUALITY);
defineRule(TokenType.TOKEN_BANGEQUAL, null, Parser.prototype.binary, Precedence.PREC_EQUALITY);
defineRule(TokenType.TOKEN_LESS, null, Parser.prototype.binary, Precedence.PREC_COMPARISON);
defineRule(TokenType.TOKEN_LESSEQUAL, null, Parser.prototype.binary, Precedence.PREC_COMPARISON);
defineRule(TokenType.TOKEN_GREATER, null, Parser.prototype.binary, Precedence.PREC_COMPARISON);
defineRule(TokenType.TOKEN_GREATEREQUAL, null, Parser.prototype.binary, Precedence.PREC_COMPARISON);
defineRule(TokenType.TOKEN_DOTDOT, null, Parser.prototype.binary, Precedence.PREC_RANGE);
defineRule(TokenType.TOKEN_DOTDOTDOT, null, Parser.prototype.binary, Precedence.PREC_RANGE);
defineRule(TokenType.TOKEN_IS, null, Parser.prototype.binary, Precedence.PREC_IS);

module.exports = {
  Compiler,
  Parser
};
