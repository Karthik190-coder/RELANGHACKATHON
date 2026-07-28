// Wren Native Modules (os, io, timer, scheduler) in JavaScript

const fs = require('fs');
const path = require('path');
const os = require('os');
const process = require('process');

const OS_MODULE_SOURCE = `
class Platform {
  foreign static homePath
  foreign static isPosix
  foreign static name
  static isWindows { name == "Windows" }
}

class Process {
  static arguments { allArguments }
  foreign static allArguments
  foreign static cwd
  foreign static pid
  foreign static version
}
`;

const TIMER_MODULE_SOURCE = `
class Timer {
  static sleep(milliseconds) {
    startTimer_(milliseconds, Fiber.current)
  }
  foreign static startTimer_(milliseconds, fiber)
}
`;

const SCHEDULER_MODULE_SOURCE = `
class Scheduler {
  static add(callable) {
    if (__scheduled == null) __scheduled = []
    __scheduled.add(Fiber.new {
      callable.call()
      runNextScheduled_()
    })
  }

  static resume_(fiber) { fiber.transfer() }
  static resume_(fiber, arg) { fiber.transfer(arg) }

  static await_(fn) {
    fn.call()
    return Scheduler.runNextScheduled_()
  }

  static runNextScheduled_() {
    if (__scheduled == null || __scheduled.isEmpty) {
      return Fiber.suspend()
    } else {
      return __scheduled.removeAt(0).transfer()
    }
  }

  static captureMethods_() {}
}
`;

const IO_MODULE_SOURCE = `
class Directory {
  static exists(path) {
    return exists_(path)
  }
  static list(path) {
    return list_(path)
  }
  foreign static exists_(path)
  foreign static list_(path)
}

class File {
  static read(path) {
    return read_(path)
  }
  static exists(path) {
    return exists_(path)
  }
  foreign static read_(path)
  foreign static exists_(path)
}
`;

function registerNativeModules(vm) {
  // Bind OS module native methods
  vm.registerModule("os", OS_MODULE_SOURCE);
  vm.bindPrimitive("Platform", "name", (vm, args) => os.platform() === 'win32' ? 'Windows' : 'Linux');
  vm.bindPrimitive("Platform", "isPosix", (vm, args) => os.platform() !== 'win32');
  vm.bindPrimitive("Platform", "homePath", (vm, args) => os.homedir());

  vm.bindPrimitive("Process", "allArguments", (vm, args) => vm.cliArgs || []);
  vm.bindPrimitive("Process", "cwd", (vm, args) => process.cwd());
  vm.bindPrimitive("Process", "pid", (vm, args) => process.pid);
  vm.bindPrimitive("Process", "version", (vm, args) => process.version);

  // Bind Timer module
  vm.registerModule("timer", TIMER_MODULE_SOURCE);
  vm.bindPrimitive("Timer", "startTimer_(2)", (vm, args) => {
    const ms = args[1];
    const fiber = args[2];
    setTimeout(() => {
      vm.resumeFiber(fiber);
    }, ms);
    return null;
  });

  // Bind Scheduler module
  vm.registerModule("scheduler", SCHEDULER_MODULE_SOURCE);

  // Bind IO module
  vm.registerModule("io", IO_MODULE_SOURCE);
  vm.bindPrimitive("File", "read_(1)", (vm, args) => {
    try {
      return fs.readFileSync(args[1], 'utf8');
    } catch (e) {
      return null;
    }
  });
  vm.bindPrimitive("File", "exists_(1)", (vm, args) => {
    return fs.existsSync(args[1]) && fs.statSync(args[1]).isFile();
  });
  vm.bindPrimitive("Directory", "exists_(1)", (vm, args) => {
    return fs.existsSync(args[1]) && fs.statSync(args[1]).isDirectory();
  });
  vm.bindPrimitive("Directory", "list_(1)", (vm, args) => {
    try {
      return fs.readdirSync(args[1]);
    } catch (e) {
      return [];
    }
  });
}

module.exports = {
  registerNativeModules
};
