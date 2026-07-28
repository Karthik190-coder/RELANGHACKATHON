// Wren Virtual Machine Core Engine in JavaScript

const OP = require('./opcodes');
const {
  ObjClass,
  ObjInstance,
  ObjString,
  ObjList,
  ObjMap,
  ObjRange,
  ObjFiber,
  ObjClosure,
  ObjUpvalue,
  wrenToString,
  isTruthy
} = require('./value');
const { Parser } = require('./compiler');
const { WREN_CORE_SOURCE, bindCorePrimitives } = require('./core');
const { registerNativeModules } = require('./modules');

class VM {
  constructor() {
    this.modules = new Map();
    this.symbols = [];
    this.symbolMap = new Map();
    this.primitives = new Map();

    this.classes = new Map();
    this.currentFiber = null;
    this.cliArgs = [];

    this.initCore();
  }

  initCore() {
    const coreClasses = ["Object", "Class", "Bool", "Num", "String", "StringByteSequence", "StringCodePointSequence", "List", "Map", "MapSequence", "MapKeySequence", "MapValueSequence", "Fn", "Fiber", "System", "Sequence", "Null", "Range", "MapEntry"];
    coreClasses.forEach(name => {
      const cls = new ObjClass(name);
      this.classes.set(name, cls);
      this.defineModuleVar("core", name, cls);
    });

    const objectClass = this.getClassByName("Object");
    const sequenceClass = this.getClassByName("Sequence");
    ["Class", "Bool", "Num", "String", "List", "Map", "Fn", "Fiber", "System", "Sequence", "Null", "Range", "MapEntry"].forEach(name => {
      const cls = this.getClassByName(name);
      if (cls) cls.superclass = objectClass;
    });
    ["String", "List", "Map", "StringByteSequence", "StringCodePointSequence", "MapSequence", "MapKeySequence", "MapValueSequence"].forEach(name => {
      const cls = this.getClassByName(name);
      if (cls) cls.superclass = sequenceClass;
    });

    bindCorePrimitives(this);
    registerNativeModules(this);

    this.interpret("core", WREN_CORE_SOURCE);
  }

  ensureSymbol(symbol) {
    if (this.symbolMap.has(symbol)) {
      return this.symbolMap.get(symbol);
    }
    const index = this.symbols.length;
    this.symbols.push(symbol);
    this.symbolMap.set(symbol, index);
    return index;
  }

  getOrCreateModule(name) {
    if (!this.modules.has(name)) {
      const module = {
        vars: [],
        varMap: new Map()
      };
      // Wren makes Core's globals visible in every module. Preserve the
      // same class objects (rather than copying them) so native dispatch and
      // user-defined class identity remain consistent across imports.
      if (name !== "core" && this.modules.has("core")) {
        const core = this.modules.get("core");
        for (const [global, index] of core.varMap.entries()) {
          module.varMap.set(global, module.vars.length);
          module.vars.push(core.vars[index]);
        }
      }
      this.modules.set(name, module);
    }
    return this.modules.get(name);
  }

  defineModuleVar(moduleName, varName, value) {
    const mod = this.getOrCreateModule(moduleName);
    if (mod.varMap.has(varName)) {
      const idx = mod.varMap.get(varName);
      mod.vars[idx] = value;
      return idx;
    }
    const idx = mod.vars.length;
    mod.vars.push(value);
    mod.varMap.set(varName, idx);
    return idx;
  }

  findModuleVar(moduleName, varName) {
    const mod = this.modules.get(moduleName);
    if (!mod || !mod.varMap.has(varName)) return -1;
    return mod.varMap.get(varName);
  }

  getClassByName(name) {
    return this.classes.get(name) || null;
  }

  getClass(value) {
    if (value === null) return this.getClassByName("Null");
    if (typeof value === "boolean") return this.getClassByName("Bool");
    if (typeof value === "number") return this.getClassByName("Num");
    if (typeof value === "string" || value instanceof ObjString) return this.getClassByName("String");
    if (value instanceof ObjList) return this.getClassByName("List");
    if (value instanceof ObjMap) return this.getClassByName("Map");
    if (value instanceof ObjRange) return this.getClassByName("Range");
    if (value instanceof ObjFiber) return this.getClassByName("Fiber");
    if (value instanceof ObjClosure) return this.getClassByName("Fn");
    if (value instanceof ObjClass) return this.getClassByName("Class");
    if (value && value.classObj) return value.classObj;
    return this.getClassByName("Object");
  }

  bindPrimitive(className, methodSymbol, nativeFn) {
    const key = `${className}.${methodSymbol}`;
    this.primitives.set(key, nativeFn);
  }

  invoke(receiver, symbol, args = []) {
    const cls = this.getClass(receiver);
    const runClosure = (closure) => {
      const previousFiber = this.currentFiber;
      const fiber = new ObjFiber(closure, this.getClassByName("Fiber"));
      fiber.stack = [receiver, ...args];
      fiber.frames[0].stackStart = 0;
      this.currentFiber = fiber;
      const ok = this.run();
      const result = fiber.stack.length > 0 ? fiber.stack[fiber.stack.length - 1] : null;
      this.currentFiber = previousFiber;
      return ok ? result : null;
    };

    if (receiver instanceof ObjClass && receiver.staticMethods && receiver.staticMethods.has(symbol)) {
      const method = receiver.staticMethods.get(symbol);
      if (typeof method === "function") {
        return method(this, [receiver, ...args]);
      }
      if (method && method.fn) {
        return runClosure(method);
      }
      return null;
    }

    let dispatchClass = cls;
    while (dispatchClass) {
      const primKey = `${dispatchClass.name}.${symbol}`;
      if (this.primitives.has(primKey)) {
        return this.primitives.get(primKey)(this, [receiver, ...args]);
      }
      dispatchClass = dispatchClass.superclass;
    }

    let methodClosure = null;
    let methodClass = cls;
    while (methodClass && !methodClosure) {
      if (methodClass.methods && methodClass.methods.has(symbol)) {
        methodClosure = methodClass.methods.get(symbol);
        break;
      }
      methodClass = methodClass.superclass;
    }

    if (!methodClosure) return null;
    if (typeof methodClosure === "function") {
      return methodClosure(this, [receiver, ...args]);
    }
    if (methodClosure && methodClosure.fn) {
      return runClosure(methodClosure);
    }
    return null;
  }

  suspendFiber() {
    if (this.currentFiber) {
      this.currentFiber.state = "SUSPENDED";
    }
    return null;
  }

  resumeFiber(fiber) {
    if (!(fiber instanceof ObjFiber)) return null;
    const previous = this.currentFiber;
    this.currentFiber = fiber;
    fiber.state = "RUNNING";
    const result = this.run();
    this.currentFiber = previous;
    return result;
  }

  abortFiber(message) {
    console.error(message === undefined ? "Fiber aborted." : wrenToString(message));
    if (this.currentFiber) {
      this.currentFiber.state = "DONE";
      this.currentFiber.error = message;
    }
    return null;
  }

  registerModule(name, source) {
    this.getOrCreateModule(name);
    this.interpret(name, source);
  }

  interpret(moduleName, source) {
    const parser = new Parser(this, moduleName, source);
    const fn = parser.parse();
    if (!fn) return false;

    const closure = new ObjClosure(fn);
    const fiber = new ObjFiber(closure);
    this.currentFiber = fiber;

    return this.run();
  }

  run() {
    const fiber = this.currentFiber;
    if (!fiber || fiber.frames.length === 0) return true;

    let frame = fiber.frames[fiber.frames.length - 1];
    let code = frame.closure.fn.code;
    let constants = frame.closure.fn.constants;
    let stack = fiber.stack;

    const readByte = () => code[frame.ip++];
    const readShort = () => (code[frame.ip++] | (code[frame.ip++] << 8));

    while (frame.ip < code.length) {
      const instruction = readByte();

      switch (instruction) {
        case OP.CONSTANT: {
          const constant = constants[readByte()];
          stack.push(constant);
          break;
        }
        case OP.NULL: stack.push(null); break;
        case OP.FALSE: stack.push(false); break;
        case OP.TRUE: stack.push(true); break;

        case OP.LOAD_LOCAL_0:
        case OP.LOAD_LOCAL_1:
        case OP.LOAD_LOCAL_2:
        case OP.LOAD_LOCAL_3:
        case OP.LOAD_LOCAL_4:
        case OP.LOAD_LOCAL_5:
        case OP.LOAD_LOCAL_6:
        case OP.LOAD_LOCAL_7:
        case OP.LOAD_LOCAL_8: {
          const slot = instruction - OP.LOAD_LOCAL_0;
          stack.push(stack[frame.stackStart + slot]);
          break;
        }

        case OP.LOAD_LOCAL: {
          const slot = readByte();
          stack.push(stack[frame.stackStart + slot]);
          break;
        }

        case OP.STORE_LOCAL: {
          const slot = readByte();
          stack[frame.stackStart + slot] = stack[stack.length - 1];
          break;
        }

        case OP.LOAD_MODULE_VAR: {
          const slot = readByte();
          const mod = this.modules.get(frame.closure.fn.module);
          stack.push(mod ? mod.vars[slot] : null);
          break;
        }

        case OP.STORE_MODULE_VAR: {
          const slot = readByte();
          const mod = this.modules.get(frame.closure.fn.module);
          if (mod) mod.vars[slot] = stack[stack.length - 1];
          break;
        }

        case OP.LOAD_FIELD_THIS: {
          const slot = readByte();
          const receiver = stack[frame.stackStart];
          stack.push(receiver && receiver.fields ? receiver.fields[slot] : null);
          break;
        }

        case OP.STORE_FIELD_THIS: {
          const slot = readByte();
          const receiver = stack[frame.stackStart];
          if (receiver && receiver.fields) receiver.fields[slot] = stack[stack.length - 1];
          break;
        }

        case OP.POP:
          stack.pop();
          break;

        case OP.JUMP: {
          const offset = readShort();
          frame.ip += offset;
          break;
        }

        case OP.LOOP: {
          const offset = readShort();
          frame.ip -= offset;
          break;
        }

        case OP.JUMP_IF: {
          const offset = readShort();
          const condition = stack.pop();
          if (!isTruthy(condition)) {
            frame.ip += offset;
          }
          break;
        }

        case OP.CALL_0:
        case OP.CALL_1:
        case OP.CALL_2:
        case OP.CALL_3:
        case OP.CALL_4:
        case OP.CALL_5:
        case OP.CALL_6:
        case OP.CALL_7:
        case OP.CALL_8:
        case OP.CALL_9:
        case OP.CALL_10:
        case OP.CALL_11:
        case OP.CALL_12:
        case OP.CALL_13:
        case OP.CALL_14:
        case OP.CALL_15:
        case OP.CALL_16: {
          const numArgs = instruction - OP.CALL_0;
          const symbolIndex = readByte();
          const symbol = this.symbols[symbolIndex];

          const args = [];
          for (let i = 0; i <= numArgs; i++) {
            args.unshift(stack.pop());
          }

          const receiver = args[0];
          const cls = this.getClass(receiver);

          if (symbol === "is(1)") {
            let target = args[1];
            let actual = this.getClass(receiver);
            let matches = false;
            while (actual) {
              if (actual === target) { matches = true; break; }
              actual = actual.superclass;
            }
            stack.push(matches);
            break;
          }

          stack.push(this.invoke(receiver, symbol, args.slice(1)));
          break;
        }

        case OP.CLASS: {
          const nameIndex = readByte();
          const name = constants[nameIndex];
          const superclass = stack.pop();
          const classObj = new ObjClass(name, superclass);
          classObj.staticMethods = new Map();
          this.classes.set(name, classObj);
          stack.push(classObj);
          break;
        }

        case OP.METHOD_INSTANCE: {
          const symbolIndex = readShort();
          const symbol = this.symbols[symbolIndex];
          const classObj = stack.pop();
          const methodObj = stack.pop();
          if (classObj && classObj.methods) {
            classObj.methods.set(symbol, methodObj);
          }
          break;
        }

        case OP.METHOD_STATIC: {
          const symbolIndex = readShort();
          const symbol = this.symbols[symbolIndex];
          const classObj = stack.pop();
          const methodObj = stack.pop();
          if (classObj && typeof classObj === 'object') {
            if (!classObj.staticMethods) classObj.staticMethods = new Map();
            classObj.staticMethods.set(symbol, methodObj);
          }
          break;
        }

        case OP.END_CLASS: {
          stack.pop();
          break;
        }

        case OP.CLOSURE: {
          const constantIndex = readByte();
          const fn = constants[constantIndex];
          const closure = new ObjClosure(fn);
          for (let i = 0; i < fn.numUpvalues; i++) {
            const isLocal = readByte() === 1;
            const index = readByte();
            closure.upvalues.push(new ObjUpvalue(index, isLocal));
          }
          stack.push(closure);
          break;
        }

        case OP.RETURN: {
          const result = stack.pop();
          fiber.frames.pop();
          if (fiber.frames.length === 0) {
            return true;
          }
          frame = fiber.frames[fiber.frames.length - 1];
          code = frame.closure.fn.code;
          constants = frame.closure.fn.constants;
          stack.push(result);
          break;
        }

        case OP.END_MODULE:
        case OP.END:
          return true;

        default:
          return true;
      }
    }

    return true;
  }
}

module.exports = { VM };
