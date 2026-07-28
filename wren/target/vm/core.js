// Wren Core Standard Library & Built-in Primitives in JavaScript

const {
  ObjClass,
  ObjInstance,
  ObjString,
  ObjList,
  ObjMap,
  ObjRange,
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

  take(count) {
    var result = []
    var index = 0
    for (element in this) {
      if (index >= count) return result
      result.add(element)
      index = index + 1
    }
    return result
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

class String {
  bytes { StringByteSequence.new(this) }
  codePoints { StringCodePointSequence.new(this) }

  endsWith(suffix) {
    if (!(suffix is String)) return false
    if (suffix.count > count) return false
    return this[count - suffix.count..-1] == suffix
  }

  trim(chars) {
    if (chars == null) chars = " \t\r\n"
    var start = 0
    var end = count - 1
    while (start <= end && chars.contains(this[start])) start = start + 1
    while (end >= start && chars.contains(this[end])) end = end - 1
    if (end < start) return ""
    return this[start..end]
  }

  trimEnd(chars) {
    if (chars == null) chars = " \t\r\n"
    var end = count - 1
    while (end >= 0 && chars.contains(this[end])) end = end - 1
    if (end < 0) return ""
    return this[0..end]
  }

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

class List {
  static filled(size, value) {
    if (!(size is Num)) {
      Fiber.abort("Size must be a number.")
    }
    if (size < 0) {
      Fiber.abort("Size cannot be negative.")
    }
    var result = List.new()
    var i = 0
    while (i < size) {
      result.add(value)
      i = i + 1
    }
    return result
  }

  addAll(other) {
    for (element in other) {
      add(element)
    }
    return other
  }

  isEmpty { count == 0 }

  iterate(iterator) { iterate_(iterator) }
  iteratorValue(iterator) { iteratorValue_(iterator) }

  remove(value) {
    var index = 0
    while (index < count) {
      if (this[index] == value) {
        removeAt(index)
        return value
      }
      index = index + 1
    }
    return null
  }

  insert(index, value) { insert_(index, value) }
  removeAt(index) { removeAt_(index) }

  sort(compare) {
    var i = 0
    while (i < count) {
      var j = i + 1
      while (j < count) {
        if (compare.call(this[j], this[i])) {
          var temp = this[i]
          this[i] = this[j]
          this[j] = temp
        }
        j = j + 1
      }
      i = i + 1
    }
    return this
  }

  sort() { sort {|a, b| a < b } }

  toString { "[%(join(", "))]" }

  +(other) {
    var result = this[0..-1]
    for (element in other) {
      result.addAll(other)
    }
    return result
  }
}

class Map {
  isEmpty { count == 0 }

  keys { MapKeySequence.new(this) }
  values { MapValueSequence.new(this) }

  iterate(iterator) { iterate_(iterator) }
  iteratorValue(iterator) { iteratorValue_(iterator) }

  containsKey(key) { containsKey_(key) }
  remove(key) { remove_(key) }

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
    System.writeString_("\n")
  }

  static print(obj) {
    System.writeObject_(obj)
    System.writeString_("\n")
    return obj
  }

  static write(obj) {
    System.writeObject_(obj)
    return obj
  }

  static writeObject_(obj) {
    var string = obj.toString
    if (string is String) {
      System.writeString_(string)
    } else {
      System.writeString_("[invalid toString]")
    }
  }
}
`;

function asNumber(value) {
  return typeof value === 'number' ? value : null;
}

function isContinuationByte(byte) {
  return (byte & 0xc0) === 0x80;
}

function utf8CharLength(firstByte) {
  if ((firstByte & 0x80) === 0) return 1;
  if ((firstByte & 0xe0) === 0xc0) return 2;
  if ((firstByte & 0xf0) === 0xe0) return 3;
  if ((firstByte & 0xf8) === 0xf0) return 4;
  return 1;
}

function utf8ByteLengthOfString(text) {
  return Buffer.byteLength(wrenToString(text), 'utf8');
}

function bufferFromWrenString(text) {
  return Buffer.from(wrenToString(text), 'utf8');
}

function decodeSingleByte(byte) {
  return Buffer.from([byte]).toString('latin1');
}

function utf8IteratorNext(buffer, iterator) {
  if (iterator === null) return buffer.length > 0 ? 0 : false;
  if (typeof iterator !== 'number' || !Number.isInteger(iterator) || iterator < 0 || iterator >= buffer.length) {
    return false;
  }

  let index = iterator;
  if (isContinuationByte(buffer[index])) {
    while (index < buffer.length && isContinuationByte(buffer[index])) index++;
    return index < buffer.length ? index : false;
  }

  const width = utf8CharLength(buffer[index]);
  if (index + width >= buffer.length) return false;
  for (let offset = 1; offset < width; offset++) {
    if (!isContinuationByte(buffer[index + offset])) {
      return index + 1;
    }
  }
  return index + width;
}

function utf8IteratorValue(buffer, iterator) {
  if (typeof iterator !== 'number' || !Number.isInteger(iterator) || iterator < 0 || iterator >= buffer.length) {
    return null;
  }

  if (isContinuationByte(buffer[iterator])) {
    return decodeSingleByte(buffer[iterator]);
  }

  const width = utf8CharLength(buffer[iterator]);
  if (iterator + width > buffer.length) {
    return decodeSingleByte(buffer[iterator]);
  }

  for (let offset = 1; offset < width; offset++) {
    if (!isContinuationByte(buffer[iterator + offset])) {
      return decodeSingleByte(buffer[iterator]);
    }
  }

  return buffer.slice(iterator, iterator + width).toString('utf8');
}

function normalizeIndex(index, size) {
  if (typeof index !== 'number' || !Number.isInteger(index)) return null;
  return index < 0 ? size + index : index;
}

function rangeBounds(range, size) {
  const from = normalizeIndex(range.from, size);
  const to = normalizeIndex(range.to, size);
  if (from === null || to === null) return null;
  return { from, to };
}

function listSlice(list, from, to, exclusive) {
  const end = exclusive ? to : to + 1;
  return new ObjList(list.elements.slice(from, end), list.classObj);
}

function stringSlice(text, from, to, exclusive) {
  const buffer = bufferFromWrenString(text);
  const end = exclusive ? to : to + 1;
  if (from < 0 || end < 0 || from > buffer.length || end > buffer.length || end < from) return null;
  return buffer.slice(from, end).toString('utf8');
}

function makeRangeValue(vm, from, to, exclusive) {
  return new ObjRange(from, to, exclusive, vm.getClassByName('Range'));
}

function makeSequenceValue(classObj, fields) {
  return Object.assign({ classObj }, fields);
}

function bindCorePrimitives(vm) {
  // Bind native methods for core classes
  vm.bindPrimitive("System", "print()", (vm, args) => {
    process.stdout.write("\n");
    return null;
  });
  vm.bindPrimitive("System", "print(1)", (vm, args) => {
    const rendered = vm.invoke(args[1], "toString", []);
    process.stdout.write(wrenToString(rendered) + "\n");
    return args[1];
  });
  vm.bindPrimitive("System", "write(1)", (vm, args) => {
    const rendered = vm.invoke(args[1], "toString", []);
    process.stdout.write(wrenToString(rendered));
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
  vm.bindPrimitive("Class", "toString", (vm, args) => args[0].name);

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
  vm.bindPrimitive("Num", "<<(1)", (vm, args) => args[0] << args[1]);
  vm.bindPrimitive("Num", ">>(1)", (vm, args) => args[0] >> args[1]);
  vm.bindPrimitive("Num", "abs", (vm, args) => Math.abs(args[0]));
  vm.bindPrimitive("Num", "ceil", (vm, args) => Math.ceil(args[0]));
  vm.bindPrimitive("Num", "floor", (vm, args) => Math.floor(args[0]));
  vm.bindPrimitive("Num", "sqrt", (vm, args) => Math.sqrt(args[0]));
  vm.bindPrimitive("Num", "isInteger", (vm, args) => Number.isInteger(args[0]));
  vm.bindPrimitive("Num", "round", (vm, args) => Math.round(args[0]));
  vm.bindPrimitive("Num", "truncate", (vm, args) => args[0] < 0 ? Math.ceil(args[0]) : Math.floor(args[0]));
  vm.bindPrimitive("Num", "fraction", (vm, args) => args[0] - (args[0] < 0 ? Math.ceil(args[0]) : Math.floor(args[0])));
  vm.bindPrimitive("Num", "smallest", (vm, args) => Number.MIN_VALUE);
  vm.bindPrimitive("Num", "pow(1)", (vm, args) => Math.pow(args[0], args[1]));
  vm.bindPrimitive("Num", "acos", (vm, args) => Math.acos(args[0]));
  vm.bindPrimitive("Num", "atan(1)", (vm, args) => Math.atan2(args[0], args[1]));
  vm.bindPrimitive("Num", "sin", (vm, args) => Math.sin(args[0]));
  vm.bindPrimitive("Num", "toString", (vm, args) => Object.is(args[0], -0) ? "-0" : args[0].toString());

  // --- String ---
  vm.bindPrimitive("String", "+(1)", (vm, args) => wrenToString(args[0]) + wrenToString(args[1]));
  vm.bindPrimitive("String", "byteCount_", (vm, args) => Buffer.byteLength(wrenToString(args[0]), 'utf8'));
  vm.bindPrimitive("String", "count", (vm, args) => wrenToString(args[0]).length);
  vm.bindPrimitive("String", "byteAt_(1)", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]);
    const index = normalizeIndex(args[1], buffer.length);
    if (index === null || index < 0 || index >= buffer.length) return null;
    return decodeSingleByte(buffer[index]);
  });
  vm.bindPrimitive("String", "iterateByte_(1)", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]);
    if (args[1] === null) return buffer.length > 0 ? 0 : false;
    if (typeof args[1] !== 'number' || !Number.isInteger(args[1]) || args[1] < 0 || args[1] >= buffer.length) {
      return false;
    }
    return args[1] + 1 < buffer.length ? args[1] + 1 : false;
  });
  vm.bindPrimitive("String", "codePointAt_(1)", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]);
    return utf8IteratorValue(buffer, args[1]);
  });
  vm.bindPrimitive("String", "iterateCodePoint_(1)", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]);
    return utf8IteratorNext(buffer, args[1]);
  });
  vm.bindPrimitive("String", "codePointCount_", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]);
    let count = 0;
    for (let index = 0; index < buffer.length;) {
      const next = utf8IteratorNext(buffer, index);
      count++;
      if (next === false) break;
      index = next;
    }
    return count;
  });
  vm.bindPrimitive("String", "[](1)", (vm, args) => {
    const text = wrenToString(args[0]);
    const buffer = bufferFromWrenString(text);
    const index = args[1];
    if (index && typeof index === 'object' && index.classObj && index.classObj.name === 'Range') {
      const bounds = rangeBounds(index, buffer.length);
      if (!bounds) return null;
      return stringSlice(text, bounds.from, bounds.to, index.exclusive);
    }
    const resolved = normalizeIndex(index, buffer.length);
    if (resolved === null || resolved < 0 || resolved >= buffer.length) return null;
    return utf8IteratorValue(buffer, resolved);
  });
  vm.bindPrimitive("String", "[](2)", (vm, args) => vm.primitives.get("String.[](1)")(vm, [args[0], args[1]]));
  vm.bindPrimitive("String", "indexOf(1)", (vm, args) => bufferFromWrenString(args[0]).indexOf(bufferFromWrenString(args[1])));
  vm.bindPrimitive("String", "indexOf(2)", (vm, args) => bufferFromWrenString(args[0]).indexOf(bufferFromWrenString(args[1]), args[2]));
  vm.bindPrimitive("String", "contains(1)", (vm, args) => bufferFromWrenString(args[0]).indexOf(bufferFromWrenString(args[1])) !== -1);
  vm.bindPrimitive("String", "endsWith(1)", (vm, args) => bufferFromWrenString(args[0]).endsWith(bufferFromWrenString(args[1])));
  vm.bindPrimitive("String", "trim(1)", (vm, args) => {
    const text = wrenToString(args[0]);
    const chars = args[1] == null ? " \t\r\n" : wrenToString(args[1]);
    let start = 0;
    let end = text.length - 1;
    while (start <= end && chars.includes(text[start])) start++;
    while (end >= start && chars.includes(text[end])) end--;
    return end < start ? "" : text.slice(start, end + 1);
  });
  vm.bindPrimitive("String", "trimEnd(1)", (vm, args) => {
    const text = wrenToString(args[0]);
    const chars = args[1] == null ? " \t\r\n" : wrenToString(args[1]);
    let end = text.length - 1;
    while (end >= 0 && chars.includes(text[end])) end--;
    return end < 0 ? "" : text.slice(0, end + 1);
  });
  vm.bindPrimitive("String", "toString", (vm, args) => args[0]);

  // --- List ---
  vm.bindPrimitive("List", "new()", (vm, args) => new ObjList([], vm.getClassByName("List")));
  vm.bindPrimitive("List", "iterate_(1)", (vm, args) => {
    const list = args[0];
    const iterator = args[1];
    if (!(list instanceof ObjList)) return false;
    if (iterator === null) return list.elements.length > 0 ? 0 : false;
    if (typeof iterator !== 'number' || !Number.isInteger(iterator)) return false;
    return iterator + 1 < list.elements.length ? iterator + 1 : false;
  });
  vm.bindPrimitive("List", "iteratorValue_(1)", (vm, args) => {
    const list = args[0];
    const iterator = args[1];
    if (!(list instanceof ObjList) || typeof iterator !== 'number' || !Number.isInteger(iterator) || iterator < 0 || iterator >= list.elements.length) {
      return null;
    }
    return list.elements[iterator];
  });
  vm.bindPrimitive("List", "add(1)", (vm, args) => {
    args[0].elements.push(args[1]);
    return args[1];
  });
  vm.bindPrimitive("List", "count", (vm, args) => args[0].elements.length);
  vm.bindPrimitive("List", "[](1)", (vm, args) => {
    const list = args[0];
    const arg = args[1];
    if (arg && typeof arg === 'object' && arg.classObj && arg.classObj.name === 'Range') {
      const bounds = rangeBounds(arg, list.elements.length);
      if (!bounds) return null;
      return listSlice(list, bounds.from, bounds.to, arg.exclusive);
    }
    const idx = normalizeIndex(arg, list.elements.length);
    if (idx === null || idx < 0 || idx >= list.elements.length) return null;
    return list.elements[idx] ?? null;
  });
  vm.bindPrimitive("List", "[]=(2)", (vm, args) => {
    const idx = normalizeIndex(args[1], args[0].elements.length);
    if (idx !== null) args[0].elements[idx] = args[2];
    return args[2];
  });
  vm.bindPrimitive("List", "clear()", (vm, args) => {
    args[0].elements = [];
    return null;
  });
  vm.bindPrimitive("List", "removeAt_(1)", (vm, args) => {
    const idx = normalizeIndex(args[1], args[0].elements.length);
    if (idx === null || idx < 0 || idx >= args[0].elements.length) return null;
    const [removed] = args[0].elements.splice(idx, 1);
    return removed ?? null;
  });
  vm.bindPrimitive("List", "insert_(2)", (vm, args) => {
    const idx = normalizeIndex(args[1], args[0].elements.length + 1);
    if (idx === null) return null;
    if (idx < 0) return null;
    args[0].elements.splice(Math.min(idx, args[0].elements.length), 0, args[2]);
    return args[2];
  });

  // --- Map ---
  vm.bindPrimitive("Map", "new()", (vm, args) => new ObjMap(vm.getClassByName("Map")));
  vm.bindPrimitive("Map", "addCore(2)", (vm, args) => {
    args[0].entries.set(args[1], args[2]);
    return args[2];
  });
  vm.bindPrimitive("Map", "iterate_(1)", (vm, args) => {
    const entries = [...args[0].entries.entries()];
    const iterator = args[1];
    if (iterator === null) return entries.length > 0 ? 0 : false;
    if (typeof iterator !== 'number' || !Number.isInteger(iterator) || iterator < 0 || iterator >= entries.length) return false;
    return iterator + 1 < entries.length ? iterator + 1 : false;
  });
  vm.bindPrimitive("Map", "iteratorValue_(1)", (vm, args) => {
    const entries = [...args[0].entries.entries()];
    const iterator = args[1];
    if (typeof iterator !== 'number' || !Number.isInteger(iterator) || iterator < 0 || iterator >= entries.length) return null;
    const [key, value] = entries[iterator];
    return new MapEntry(key, value, vm.getClassByName("MapEntry"));
  });
  vm.bindPrimitive("Map", "[](1)", (vm, args) => args[0].entries.get(args[1]) ?? null);
  vm.bindPrimitive("Map", "[]=(2)", (vm, args) => {
    args[0].entries.set(args[1], args[2]);
    return args[2];
  });
  vm.bindPrimitive("Map", "count", (vm, args) => args[0].entries.size);
  vm.bindPrimitive("Map", "containsKey_(1)", (vm, args) => args[0].entries.has(args[1]));
  vm.bindPrimitive("Map", "remove_(1)", (vm, args) => {
    const value = args[0].entries.get(args[1]);
    const existed = args[0].entries.delete(args[1]);
    return existed ? value : null;
  });

  // --- Range ---
  vm.bindPrimitive("Range", "contains(1)", (vm, args) => {
    const range = args[0];
    const value = args[1];
    const start = range.from;
    const end = range.to;
    if (range.exclusive) {
      return start <= end ? (value >= start && value < end) : (value <= start && value > end);
    }
    return start <= end ? (value >= start && value <= end) : (value <= start && value >= end);
  });
  vm.bindPrimitive("Range", "to", (vm, args) => args[0].to);
  vm.bindPrimitive("Range", "isInclusive", (vm, args) => !args[0].exclusive);
  vm.bindPrimitive("Range", "toString", (vm, args) => args[0].toString());
  vm.bindPrimitive("Range", "iterate(1)", (vm, args) => {
    const range = args[0];
    const iterator = args[1];
    const step = range.from <= range.to ? 1 : -1;
    const boundary = range.exclusive ? range.to : range.to + step;
    if (iterator === null) return range.from;
    if (typeof iterator !== 'number' || !Number.isInteger(iterator)) return false;
    const next = iterator + step;
    if (step > 0) {
      return range.exclusive ? (next < range.to ? next : false) : (next <= range.to ? next : false);
    }
    return range.exclusive ? (next > range.to ? next : false) : (next >= range.to ? next : false);
  });
  vm.bindPrimitive("Range", "iteratorValue(1)", (vm, args) => args[1]);

  // --- MapEntry ---
  vm.bindPrimitive("MapEntry", "new(2)", (vm, args) => new MapEntry(args[1], args[2], vm.getClassByName("MapEntry")));

  // --- Helper sequence classes ---
  vm.bindPrimitive("MapSequence", "new(2)", (vm, args) => makeSequenceValue(vm.getClassByName("MapSequence"), { _sequence: args[1], _fn: args[2] }));
  vm.bindPrimitive("MapKeySequence", "new(1)", (vm, args) => makeSequenceValue(vm.getClassByName("MapKeySequence"), { _map: args[1] }));
  vm.bindPrimitive("MapValueSequence", "new(1)", (vm, args) => makeSequenceValue(vm.getClassByName("MapValueSequence"), { _map: args[1] }));
  vm.bindPrimitive("StringByteSequence", "new(1)", (vm, args) => makeSequenceValue(vm.getClassByName("StringByteSequence"), { _string: args[1] }));
  vm.bindPrimitive("StringCodePointSequence", "new(1)", (vm, args) => makeSequenceValue(vm.getClassByName("StringCodePointSequence"), { _string: args[1] }));
  vm.bindPrimitive("MapSequence", "iterate(1)", (vm, args) => args[0]._sequence.iterate(args[1]));
  vm.bindPrimitive("MapSequence", "iteratorValue(1)", (vm, args) => args[0]._fn.call(args[0]._sequence.iteratorValue(args[1])));
  vm.bindPrimitive("MapKeySequence", "iterate(1)", (vm, args) => args[0]._map.iterate(args[1]));
  vm.bindPrimitive("MapKeySequence", "iteratorValue(1)", (vm, args) => args[0]._map.iteratorValue(args[1]).key);
  vm.bindPrimitive("MapValueSequence", "iterate(1)", (vm, args) => args[0]._map.iterate(args[1]));
  vm.bindPrimitive("MapValueSequence", "iteratorValue(1)", (vm, args) => args[0]._map.iteratorValue(args[1]).value);
  vm.bindPrimitive("StringByteSequence", "[](1)", (vm, args) => bufferFromWrenString(args[0]._string)[args[1]]);
  vm.bindPrimitive("StringByteSequence", "iterate(1)", (vm, args) => utf8IteratorNext(bufferFromWrenString(args[0]._string), args[1]));
  vm.bindPrimitive("StringByteSequence", "iteratorValue(1)", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]._string);
    const index = args[1];
    if (typeof index !== 'number' || !Number.isInteger(index) || index < 0 || index >= buffer.length) return null;
    return decodeSingleByte(buffer[index]);
  });
  vm.bindPrimitive("StringByteSequence", "count", (vm, args) => utf8ByteLengthOfString(args[0]._string));
  vm.bindPrimitive("StringCodePointSequence", "[](1)", (vm, args) => utf8IteratorValue(bufferFromWrenString(args[0]._string), args[1]));
  vm.bindPrimitive("StringCodePointSequence", "iterate(1)", (vm, args) => utf8IteratorNext(bufferFromWrenString(args[0]._string), args[1]));
  vm.bindPrimitive("StringCodePointSequence", "iteratorValue(1)", (vm, args) => utf8IteratorValue(bufferFromWrenString(args[0]._string), args[1]));
  vm.bindPrimitive("StringCodePointSequence", "count", (vm, args) => {
    const buffer = bufferFromWrenString(args[0]._string);
    let count = 0;
    for (let index = 0; index < buffer.length;) {
      const next = utf8IteratorNext(buffer, index);
      count++;
      if (next === false) break;
      index = next;
    }
    return count;
  });

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
