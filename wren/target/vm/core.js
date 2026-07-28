// Wren Core Standard Library & Built-in Primitives in JavaScript

const {
  ObjClass,
  ObjInstance,
  ObjString,
  ObjList,
  ObjMap,
  ObjFiber,
  ObjClosure,
  ClassAttributes,
  MapEntry,
  wrenToString,
  isTruthy
} = require('./value');

const WREN_CORE_SOURCE = `
class Bool {}
class Fiber {}
class Fn {}
class Null {}
class Num {}

class Sequence {
  all(f) {
    var result = true
    for (element in this) {
      result = f.call(element)
      if (!result) return result
    }
    return result
  }

  any(f) {
    var result = false
    for (element in this) {
      result = f.call(element)
      if (result) return result
    }
    return result
  }

  contains(element) {
    for (item in this) {
      if (element == item) return true
    }
    return false
  }

  count {
    var result = 0
    for (element in this) {
      result = result + 1
    }
    return result
  }

  each(f) {
    for (element in this) {
      f.call(element)
    }
  }

  isEmpty { iterate(null) ? false : true }

  map(transformation) { MapSequence.new(this, transformation) }

  reduce(acc, f) {
    for (element in this) {
      acc = f.call(acc, element)
    }
    return acc
  }

  join() { join("") }

  join(sep) {
    var first = true
    var result = ""
    for (element in this) {
      if (!first) result = result + sep
      first = false
      result = result + element.toString
    }
    return result
  }

  toList {
    var result = List.new()
    for (element in this) {
      result.add(element)
    }
    return result
  }
}

class MapSequence is Sequence {
  construct new(sequence, fn) {
    _sequence = sequence
    _fn = fn
  }

  iterate(iterator) { _sequence.iterate(iterator) }
  iteratorValue(iterator) { _fn.call(_sequence.iteratorValue(iterator)) }
}

class String is Sequence {
  bytes { StringByteSequence.new(this) }

  split(delimiter) {
    if (!(delimiter is String) || delimiter.isEmpty) {
      Fiber.abort("Delimiter must be a non-empty string.")
    }

    var result = []
    var last = 0
    var index = 0
    var delimSize = delimiter.byteCount_
    var size = byteCount_

    while (last < size && (index = indexOf(delimiter, last)) != -1) {
      result.add(this[last...index])
      last = index + delimSize
    }

    if (last < size) {
      result.add(this[last..-1])
    } else {
      result.add("")
    }
    return result
  }

  replace(from, to) {
    if (!(from is String) || from.isEmpty) {
      Fiber.abort("From must be a non-empty string.")
    } else if (!(to is String)) {
      Fiber.abort("To must be a string.")
    }

    var result = ""
    var last = 0
    var index = 0
    var fromSize = from.byteCount_
    var size = byteCount_

    while (last < size && (index = indexOf(from, last)) != -1) {
      result = result + this[last...index] + to
      last = index + fromSize
    }

    if (last < size) result = result + this[last..-1]

    return result
  }
}

class StringByteSequence is Sequence {
  construct new(string) {
    _string = string
  }

  [index] { _string.byteAt_(index) }
  iterate(iterator) { _string.iterateByte_(iterator) }
  iteratorValue(iterator) { _string.byteAt_(iterator) }
  count { _string.byteCount_ }
}

class List is Sequence {
  addAll(other) {
    for (element in other) {
      add(element)
    }
    return other
  }

  toString { "[%(join(", "))]" }

  +(other) {
    var result = this[0..-1]
    for (element in other) {
      result.addAll(other)
    }
    return result
  }
}

class Map is Sequence {
  toString {
    var first = true
    var result = "{"
    for (key in keys) {
      if (!first) result = result + ", "
      first = false
      result = result + "%(key): %(this[key])"
    }
    return result + "}"
  }
}

class System {
  static print() {
    writeString_("\n")
  }

  static print(obj) {
    writeObject_(obj)
    writeString_("\n")
    return obj
  }

  static write(obj) {
    writeObject_(obj)
    return obj
  }

  static writeObject_(obj) {
    var string = obj.toString
    if (string is String) {
      writeString_(string)
    } else {
      writeString_("[invalid toString]")
    }
  }
}
`;

function bindCorePrimitives(vm) {
  // Bind native methods for core classes

  // --- System ---
  vm.bindPrimitive("System", "print()", (vm, args) => {
    process.stdout.write("\n");
    return null;
  });
  vm.bindPrimitive("System", "print(1)", (vm, args) => {
    process.stdout.write(wrenToString(args[1]) + "\n");
    return args[1];
  });
  vm.bindPrimitive("System", "write(1)", (vm, args) => {
    process.stdout.write(wrenToString(args[1]));
    return args[1];
  });
  vm.bindPrimitive("System", "writeString_(1)", (vm, args) => {
    const str = wrenToString(args[1]);
    process.stdout.write(str);
    return null;
  });

  vm.bindPrimitive("System", "clock", (vm, args) => {
    return Date.now() / 1000.0;
  });

  // --- Object ---
  vm.bindPrimitive("Object", "same(1)", (vm, args) => args[0] === args[1]);
  vm.bindPrimitive("Object", "toString", (vm, args) => wrenToString(args[0]));
  vm.bindPrimitive("Object", "type", (vm, args) => vm.getClass(args[0]));
  vm.bindPrimitive("Object", "!(0)", (vm, args) => !isTruthy(args[0]));
  vm.bindPrimitive("Object", "==(1)", (vm, args) => args[0] === args[1]);
  vm.bindPrimitive("Object", "!=(1)", (vm, args) => args[0] !== args[1]);

  // --- Num ---
  vm.bindPrimitive("Num", "+(1)", (vm, args) => args[0] + args[1]);
  vm.bindPrimitive("Num", "-(1)", (vm, args) => args[0] - args[1]);
  vm.bindPrimitive("Num", "*(1)", (vm, args) => args[0] * args[1]);
  vm.bindPrimitive("Num", "/(1)", (vm, args) => args[0] / args[1]);
  vm.bindPrimitive("Num", "%(1)", (vm, args) => args[0] % args[1]);
  vm.bindPrimitive("Num", "<(1)", (vm, args) => args[0] < args[1]);
  vm.bindPrimitive("Num", "<=(1)", (vm, args) => args[0] <= args[1]);
  vm.bindPrimitive("Num", ">(1)", (vm, args) => args[0] > args[1]);
  vm.bindPrimitive("Num", ">=(1)", (vm, args) => args[0] >= args[1]);
  vm.bindPrimitive("Num", "&(1)", (vm, args) => args[0] & args[1]);
  vm.bindPrimitive("Num", "|(1)", (vm, args) => args[0] | args[1]);
  vm.bindPrimitive("Num", "^(1)", (vm, args) => args[0] ^ args[1]);
  vm.bindPrimitive("Num", "~(0)", (vm, args) => ~args[0]);
  vm.bindPrimitive("Num", "-(0)", (vm, args) => -args[0]);
  vm.bindPrimitive("Num", "abs", (vm, args) => Math.abs(args[0]));
  vm.bindPrimitive("Num", "ceil", (vm, args) => Math.ceil(args[0]));
  vm.bindPrimitive("Num", "floor", (vm, args) => Math.floor(args[0]));
  vm.bindPrimitive("Num", "sqrt", (vm, args) => Math.sqrt(args[0]));
  vm.bindPrimitive("Num", "isInteger", (vm, args) => Number.isInteger(args[0]));
  vm.bindPrimitive("Num", "toString", (vm, args) => args[0].toString());

  // --- String ---
  vm.bindPrimitive("String", "+(1)", (vm, args) => wrenToString(args[0]) + wrenToString(args[1]));
  vm.bindPrimitive("String", "byteCount_", (vm, args) => Buffer.byteLength(wrenToString(args[0]), 'utf8'));
  vm.bindPrimitive("String", "count", (vm, args) => wrenToString(args[0]).length);
  vm.bindPrimitive("String", "indexOf(1)", (vm, args) => wrenToString(args[0]).indexOf(wrenToString(args[1])));
  vm.bindPrimitive("String", "indexOf(2)", (vm, args) => wrenToString(args[0]).indexOf(wrenToString(args[1]), args[2]));
  vm.bindPrimitive("String", "contains(1)", (vm, args) => wrenToString(args[0]).includes(wrenToString(args[1])));
  vm.bindPrimitive("String", "toString", (vm, args) => args[0]);

  // --- List ---
  vm.bindPrimitive("List", "new()", (vm, args) => new ObjList([], vm.getClassByName("List")));
  vm.bindPrimitive("List", "add(1)", (vm, args) => {
    args[0].elements.push(args[1]);
    return args[1];
  });
  vm.bindPrimitive("List", "count", (vm, args) => args[0].elements.length);
  vm.bindPrimitive("List", "[](1)", (vm, args) => {
    const idx = args[1] < 0 ? args[0].elements.length + args[1] : args[1];
    return args[0].elements[idx] ?? null;
  });
  vm.bindPrimitive("List", "[]=(2)", (vm, args) => {
    const idx = args[1] < 0 ? args[0].elements.length + args[1] : args[1];
    args[0].elements[idx] = args[2];
    return args[2];
  });
  vm.bindPrimitive("List", "clear()", (vm, args) => {
    args[0].elements = [];
    return null;
  });

  // --- Map ---
  vm.bindPrimitive("Map", "new()", (vm, args) => new ObjMap(vm.getClassByName("Map")));
  vm.bindPrimitive("Map", "addCore(2)", (vm, args) => {
    args[0].entries.set(args[1], args[2]);
    return args[2];
  });
  vm.bindPrimitive("Map", "[](1)", (vm, args) => args[0].entries.get(args[1]) ?? null);
  vm.bindPrimitive("Map", "[]=(2)", (vm, args) => {
    args[0].entries.set(args[1], args[2]);
    return args[2];
  });
  vm.bindPrimitive("Map", "count", (vm, args) => args[0].entries.size);

  // --- Fiber ---
  vm.bindPrimitive("Fiber", "new(1)", (vm, args) => new ObjFiber(args[1], vm.getClassByName("Fiber")));
  vm.bindPrimitive("Fiber", "current", (vm, args) => vm.currentFiber);
  vm.bindPrimitive("Fiber", "suspend()", (vm, args) => vm.suspendFiber());
  vm.bindPrimitive("Fiber", "abort(1)", (vm, args) => vm.abortFiber(args[1]));
}

module.exports = {
  WREN_CORE_SOURCE,
  bindCorePrimitives
};
