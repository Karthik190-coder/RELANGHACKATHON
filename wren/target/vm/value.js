// Wren Value and Object definitions in JavaScript

class ObjHeader {
  constructor(classObj) {
    this.classObj = classObj;
  }
}

class ObjString extends ObjHeader {
  constructor(value, classObj = null) {
    super(classObj);
    this.value = value;
  }

  toString() {
    return this.value;
  }
}

class ObjList extends ObjHeader {
  constructor(elements = [], classObj = null) {
    super(classObj);
    this.elements = elements;
  }
}

class ObjMap extends ObjHeader {
  constructor(classObj = null) {
    super(classObj);
    // Use Map to preserve insertion order and support arbitrary key types
    this.entries = new Map();
  }
}

class ObjFn extends ObjHeader {
  constructor(name = "", arity = 0, numLocals = 0, stackMax = 0, classObj = null) {
    super(classObj);
    this.name = name;
    this.arity = arity;
    this.numUpvalues = 0;
    this.code = []; // Uint8Array or Array of bytecodes
    this.constants = []; // Array of Values
    this.upvalues = []; // Information about upvalues for compiler
    this.debugName = name;
    this.module = null; // Reference to host module
  }
}

class ObjClosure extends ObjHeader {
  constructor(fn, classObj = null) {
    super(classObj);
    this.fn = fn;
    this.upvalues = []; // ObjUpvalue instances
  }
}

class ObjUpvalue extends ObjHeader {
  constructor(location, index, isLocal = false) {
    super(null);
    this.location = location; // Index in stack or value if closed
    this.isClosed = false;
    this.closedValue = null;
    this.index = index;
  }
}

class ObjClass extends ObjHeader {
  constructor(name, superclass = null, numFields = 0, classObj = null) {
    super(classObj);
    this.name = name;
    this.superclass = superclass;
    this.numFields = numFields;
    this.methods = new Map(); // Symbol ID -> ObjClosure / NativeFn
    this.attributes = null;
    this.isForeign = false;
  }
}

class ObjInstance extends ObjHeader {
  constructor(classObj) {
    super(classObj);
    this.fields = new Array(classObj.numFields).fill(null);
  }
}

class ObjForeign extends ObjHeader {
  constructor(classObj, data = null) {
    super(classObj);
    this.data = data;
  }
}

class ObjFiber extends ObjHeader {
  constructor(closure = null, classObj = null) {
    super(classObj);
    this.stack = [];
    this.frames = [];
    this.caller = null;
    this.error = null;
    this.state = "SUSPENDED"; // SUSPENDED, RUNNING, TRY, DONE
    
    if (closure) {
      this.pushFrame(closure, 0);
    }
  }

  pushFrame(closure, stackStart) {
    this.frames.push({
      closure,
      ip: 0,
      stackStart
    });
  }
}

class ClassAttributes extends ObjHeader {
  constructor(attributes, methods, classObj = null) {
    super(classObj);
    this.attributes = attributes;
    this.methods = methods;
  }

  toString() {
    return `attributes:${this.attributes} methods:${this.methods}`;
  }
}

class MapEntry extends ObjHeader {
  constructor(key, value, classObj = null) {
    super(classObj);
    this.key = key;
    this.value = value;
  }

  toString() {
    return `${this.key}:${this.value}`;
  }
}

// Helper functions for Wren values
function isTruthy(val) {
  if (val === null || val === false) return false;
  return true;
}

function wrenToString(val) {
  if (val === null) return "null";
  if (typeof val === "boolean") return val ? "true" : "false";
  if (typeof val === "number") return val.toString();
  if (typeof val === "string") return val;
  if (val && typeof val.toString === "function") return val.toString();
  return "[object]";
}

module.exports = {
  ObjHeader,
  ObjString,
  ObjList,
  ObjMap,
  ObjFn,
  ObjClosure,
  ObjUpvalue,
  ObjClass,
  ObjInstance,
  ObjForeign,
  ObjFiber,
  ClassAttributes,
  MapEntry,
  isTruthy,
  wrenToString
};
