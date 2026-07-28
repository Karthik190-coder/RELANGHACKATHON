const fs = require('fs');
const { stdin, stdout, exit, argv } = process;

const KILO_VERSION = '0.0.1';

const HL = {
  NORMAL: 0,
  NONPRINT: 1,
  COMMENT: 2,
  MLCOMMENT: 3,
  KEYWORD1: 4,
  KEYWORD2: 5,
  STRING: 6,
  NUMBER: 7,
  MATCH: 8,
};

const KEY = {
  NULL: 0,
  CTRL_C: 3,
  CTRL_D: 4,
  CTRL_F: 6,
  CTRL_H: 8,
  TAB: 9,
  CTRL_L: 12,
  ENTER: 13,
  CTRL_Q: 17,
  CTRL_S: 19,
  CTRL_U: 21,
  ESC: 27,
  BACKSPACE: 127,
  ARROW_LEFT: 1000,
  ARROW_RIGHT: 1001,
  ARROW_UP: 1002,
  ARROW_DOWN: 1003,
  DEL_KEY: 1004,
  HOME_KEY: 1005,
  END_KEY: 1006,
  PAGE_UP: 1007,
  PAGE_DOWN: 1008,
};

const E = {
  cx: 0,
  cy: 0,
  rowoff: 0,
  coloff: 0,
  screenrows: 24,
  screencols: 80,
  numrows: 0,
  row: [],
  dirty: 0,
  filename: null,
  statusmsg: '',
  statusmsg_time: 0,
  syntax: null,
};

const C_HL_extensions = ['.c', '.h', '.cpp', '.hpp', '.cc'];
const C_HL_keywords = [
  'auto', 'break', 'case', 'continue', 'default', 'do', 'else', 'enum',
  'extern', 'for', 'goto', 'if', 'register', 'return', 'sizeof', 'static',
  'struct', 'switch', 'typedef', 'union', 'volatile', 'while', 'NULL',
  'alignas', 'alignof', 'and', 'and_eq', 'asm', 'bitand', 'bitor', 'class',
  'compl', 'constexpr', 'const_cast', 'deltype', 'delete', 'dynamic_cast',
  'explicit', 'export', 'false', 'friend', 'inline', 'mutable', 'namespace',
  'new', 'noexcept', 'not', 'not_eq', 'nullptr', 'operator', 'or', 'or_eq',
  'private', 'protected', 'public', 'reinterpret_cast', 'static_assert',
  'static_cast', 'template', 'this', 'thread_local', 'throw', 'true', 'try',
  'typeid', 'typename', 'virtual', 'xor', 'xor_eq',
  'int|', 'long|', 'double|', 'float|', 'char|', 'unsigned|', 'signed|',
  'void|', 'short|', 'auto|', 'const|', 'bool|',
];

const HLDB = [
  {
    filematch: C_HL_extensions,
    keywords: C_HL_keywords,
    scs: '//',
    mcs: '/*',
    mce: '*/',
    flags: (1 << 0) | (1 << 1),
  },
];

let rawMode = false;

function enableRawMode() {
  if (rawMode) return;
  if (!stdin.isTTY) {
    console.error('Not a terminal');
    exit(1);
  }
  stdin.setRawMode(true);
  rawMode = true;
}

function disableRawMode() {
  if (rawMode) {
    stdin.setRawMode(false);
    rawMode = false;
  }
}

let stdinBuf = [];
let stdinResolve = null;

stdin.on('data', (data) => {
  for (let i = 0; i < data.length; i++) {
    stdinBuf.push(data[i]);
  }
  if (stdinResolve) {
    stdinResolve();
    stdinResolve = null;
  }
});

function readByte() {
  return new Promise((resolve) => {
    if (stdinBuf.length > 0) {
      resolve(stdinBuf.shift());
    } else {
      stdinResolve = () => {
        resolve(stdinBuf.shift());
        stdinResolve = null;
      };
    }
  });
}

async function editorReadKey() {
  let c;
  do {
    c = await readByte();
  } while (c === 0);

  while (true) {
    if (c !== KEY.ESC) return c;

    let seq = [];
    seq.push(await readByte());
    if (seq[0] === undefined) return KEY.ESC;
    seq.push(await readByte());
    if (seq[1] === undefined) return KEY.ESC;

    if (seq[0] === 0x5b) {
      if (seq[1] >= 0x30 && seq[1] <= 0x39) {
        let b = await readByte();
        if (b === undefined) return KEY.ESC;
        if (b === 0x7e) {
          switch (seq[1]) {
            case 0x33: return KEY.DEL_KEY;
            case 0x35: return KEY.PAGE_UP;
            case 0x36: return KEY.PAGE_DOWN;
          }
        }
      } else {
        switch (seq[1]) {
          case 0x41: return KEY.ARROW_UP;
          case 0x42: return KEY.ARROW_DOWN;
          case 0x43: return KEY.ARROW_RIGHT;
          case 0x44: return KEY.ARROW_LEFT;
          case 0x48: return KEY.HOME_KEY;
          case 0x46: return KEY.END_KEY;
        }
      }
    } else if (seq[0] === 0x4f) {
      switch (seq[1]) {
        case 0x48: return KEY.HOME_KEY;
        case 0x46: return KEY.END_KEY;
      }
    }

    return KEY.ESC;
  }
}

async function getCursorPosition() {
  stdout.write('\x1b[6n');
  let buf = '';
  while (true) {
    let b = await readByte();
    buf += String.fromCharCode(b);
    if (b === 0x52) break;
  }
  if (buf.length < 3 || buf.charCodeAt(0) !== KEY.ESC || buf[1] !== '[') return -1;
  let m = buf.match(/\[(\d+);(\d+)R/);
  if (!m) return -1;
  return { row: parseInt(m[1]), col: parseInt(m[2]) };
}

function getWindowSize() {
  if (stdout.columns && stdout.rows) {
    E.screencols = stdout.columns;
    E.screenrows = stdout.rows;
    return 0;
  }
  return -1;
}

function isSeparator(c) {
  return c === '\0' || c === ' ' || /[,.()+\-/*=~%\[\];]/.test(c);
}

function editorRowHasOpenComment(row) {
  if (row.hl && row.rsize > 0 && row.hl[row.rsize - 1] === HL.MLCOMMENT &&
    (row.rsize < 2 || (row.render[row.rsize - 2] !== '*' ||
      row.render[row.rsize - 1] !== '/'))) {
    return true;
  }
  return false;
}

function editorUpdateSyntax(row) {
  row.hl = new Uint8Array(row.rsize).fill(HL.NORMAL);

  if (!E.syntax) return;

  let keywords = E.syntax.keywords;
  let scs = E.syntax.scs;
  let mcs = E.syntax.mcs;
  let mce = E.syntax.mce;

  let p = row.render;
  let i = 0;
  while (i < p.length && (p[i] === ' ' || p[i] === '\t')) {
    i++;
  }
  let prev_sep = true;
  let in_string = 0;
  let in_comment = false;

  if (row.idx > 0 && editorRowHasOpenComment(E.row[row.idx - 1])) {
    in_comment = true;
  }

  while (i < p.length) {
    if (prev_sep && p[i] === scs[0] && p[i + 1] === scs[1]) {
      for (let j = i; j < p.length; j++) row.hl[j] = HL.COMMENT;
      break;
    }

    if (in_comment) {
      row.hl[i] = HL.MLCOMMENT;
      if (p[i] === mce[0] && p[i + 1] === mce[1]) {
        row.hl[i + 1] = HL.MLCOMMENT;
        i += 2;
        prev_sep = true;
        in_comment = false;
        continue;
      } else {
        prev_sep = false;
        i++;
        continue;
      }
    } else if (p[i] === mcs[0] && p[i + 1] === mcs[1]) {
      row.hl[i] = HL.MLCOMMENT;
      row.hl[i + 1] = HL.MLCOMMENT;
      i += 2;
      in_comment = true;
      prev_sep = false;
      continue;
    }

    if (in_string) {
      row.hl[i] = HL.STRING;
      if (p[i] === '\\') {
        row.hl[i + 1] = HL.STRING;
        i += 2;
        prev_sep = false;
        continue;
      }
      if (p[i] === in_string) in_string = 0;
      i++;
      continue;
    } else {
      if (p[i] === '"' || p[i] === "'") {
        in_string = p[i];
        row.hl[i] = HL.STRING;
        i++;
        prev_sep = false;
        continue;
      }
    }

    let ch = p.charCodeAt(i);
    if (ch < 32 || ch === 127) {
      row.hl[i] = HL.NONPRINT;
      i++;
      prev_sep = false;
      continue;
    }

    if ((ch >= 48 && ch <= 57) && (prev_sep || (i > 0 && row.hl[i - 1] === HL.NUMBER)) ||
      (ch === 0x2e && i > 0 && row.hl[i - 1] === HL.NUMBER)) {
      row.hl[i] = HL.NUMBER;
      i++;
      prev_sep = false;
      continue;
    }

    if (prev_sep) {
      let matched = false;
      for (let j = 0; j < keywords.length; j++) {
        let kw = keywords[j];
        let kw2 = kw.endsWith('|');
        let klen = kw2 ? kw.length - 1 : kw.length;
        if (kw.length === 0) continue;
        let kwStart = kw;
        if (kw2) kwStart = kw.slice(0, -1);

        if (p.slice(i, i + klen) === kwStart) {
          let nextChar = p[i + klen] || '\0';
          if (isSeparator(nextChar)) {
            let hlType = kw2 ? HL.KEYWORD2 : HL.KEYWORD1;
            for (let k = 0; k < klen; k++) row.hl[i + k] = hlType;
            i += klen;
            matched = true;
            break;
          }
        }
      }
      if (matched) {
        prev_sep = false;
        continue;
      }
    }

    prev_sep = isSeparator(p[i]);
    i++;
  }

  let oc = editorRowHasOpenComment(row);
  if (row.hl_oc !== oc && row.idx + 1 < E.numrows) {
    editorUpdateSyntax(E.row[row.idx + 1]);
  }
  row.hl_oc = oc;
}

function editorSyntaxToColor(hl) {
  switch (hl) {
    case HL.COMMENT:
    case HL.MLCOMMENT: return 36;
    case HL.KEYWORD1: return 33;
    case HL.KEYWORD2: return 32;
    case HL.STRING: return 35;
    case HL.NUMBER: return 31;
    case HL.MATCH: return 34;
    default: return 37;
  }
}

function editorSelectSyntaxHighlight(filename) {
  for (let j = 0; j < HLDB.length; j++) {
    let s = HLDB[j];
    for (let i = 0; i < s.filematch.length; i++) {
      let pat = s.filematch[i];
      let idx = filename.lastIndexOf(pat);
      if (idx !== -1) {
        if (pat[0] !== '.' || idx + pat.length === filename.length) {
          E.syntax = s;
          return;
        }
      }
    }
  }
}

function editorUpdateRow(row) {
  let render = '';
  for (let j = 0; j < row.chars.length; j++) {
    if (row.chars[j] === '\t') {
      render += ' ';
      while ((render.length + 1) % 8 !== 0) render += ' ';
    } else {
      render += row.chars[j];
    }
  }

  if (render.length > 0xffffffff) {
    console.error('Some line of the edited file is too long for kilo');
    exit(1);
  }

  row.render = render;
  row.rsize = render.length;
  editorUpdateSyntax(row);
}

function editorInsertRow(at, s) {
  if (at > E.numrows) return;
  let newRow = { idx: at, chars: s, size: s.length, render: '', rsize: 0, hl: null, hl_oc: false };
  E.row.splice(at, 0, newRow);
  for (let j = at + 1; j <= E.numrows; j++) E.row[j].idx++;
  editorUpdateRow(newRow);
  E.numrows++;
  E.dirty++;
}

function editorFreeRow(row) {
  row.render = null;
  row.chars = null;
  row.hl = null;
}

function editorDelRow(at) {
  if (at >= E.numrows) return;
  editorFreeRow(E.row[at]);
  E.row.splice(at, 1);
  for (let j = at; j < E.numrows - 1; j++) E.row[j].idx++;
  E.numrows--;
  E.dirty++;
}

function editorRowsToString() {
  let totlen = 0;
  for (let j = 0; j < E.numrows; j++) totlen += E.row[j].size + 1;
  let buf = Buffer.alloc(totlen);
  let offset = 0;
  for (let j = 0; j < E.numrows; j++) {
    buf.write(E.row[j].chars, offset, E.row[j].size, 'utf8');
    offset += E.row[j].size;
    buf[offset] = 0x0a;
    offset++;
  }
  return buf;
}

function editorRowInsertChar(row, at, c) {
  if (at > row.size) {
    let padlen = at - row.size;
    row.chars += ' '.repeat(padlen) + c;
    row.size = row.chars.length;
  } else {
    row.chars = row.chars.slice(0, at) + c + row.chars.slice(at);
    row.size++;
  }
  editorUpdateRow(row);
  E.dirty++;
}

function editorRowAppendString(row, s) {
  row.chars += s;
  row.size = row.chars.length;
  editorUpdateRow(row);
  E.dirty++;
}

function editorRowDelChar(row, at) {
  if (row.size <= at) return;
  row.chars = row.chars.slice(0, at) + row.chars.slice(at + 1);
  editorUpdateRow(row);
  row.size--;
  E.dirty++;
}

function editorInsertChar(c) {
  let filerow = E.rowoff + E.cy;
  let filecol = E.coloff + E.cx;
  let row = filerow >= E.numrows ? null : E.row[filerow];

  if (!row) {
    while (E.numrows <= filerow) editorInsertRow(E.numrows, '');
  }
  row = E.row[filerow];
  editorRowInsertChar(row, filecol, c);
  if (E.cx === E.screencols - 1)
    E.coloff++;
  else
    E.cx++;
  E.dirty++;
}

function editorInsertNewline() {
  let filerow = E.rowoff + E.cy;
  let filecol = E.coloff + E.cx;
  let row = filerow >= E.numrows ? null : E.row[filerow];

  if (!row) {
    if (filerow === E.numrows) {
      editorInsertRow(filerow, '');
      E.cx = 0;
      E.coloff = 0;
      if (E.cy === E.screenrows - 1) E.rowoff++;
      else E.cy++;
      return;
    }
    return;
  }

  if (filecol >= row.size) filecol = row.size;
  if (filecol === 0) {
    editorInsertRow(filerow, '');
  } else {
    editorInsertRow(filerow + 1, row.chars.slice(filecol));
    row.chars = row.chars.slice(0, filecol);
    row.size = filecol;
    editorUpdateRow(row);
  }

  if (E.cy === E.screenrows - 1) E.rowoff++;
  else E.cy++;
  E.cx = 0;
  E.coloff = 0;
}

function editorDelChar() {
  let filerow = E.rowoff + E.cy;
  let filecol = E.coloff + E.cx;
  let row = filerow >= E.numrows ? null : E.row[filerow];

  if (!row || (filecol === 0 && filerow === 0)) return;
  if (filecol === 0) {
    filecol = E.row[filerow - 1].size;
    editorRowAppendString(E.row[filerow - 1], row.chars);
    editorDelRow(filerow);
    if (E.cy === 0) E.rowoff--;
    else E.cy--;
    E.cx = filecol;
    if (E.cx >= E.screencols) {
      let shift = E.cx - E.screencols + 1;
      E.cx -= shift;
      E.coloff += shift;
    }
  } else {
    editorRowDelChar(row, filecol - 1);
    if (E.cx === 0 && E.coloff) E.coloff--;
    else E.cx--;
  }
  if (row) editorUpdateRow(row);
  E.dirty++;
}

function editorOpen(filename) {
  E.dirty = 0;
  E.filename = filename;

  try {
    let content = fs.readFileSync(filename, 'utf8');
    let lines = content.split('\n');
    if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];
      if (line.endsWith('\r')) line = line.slice(0, -1);
      editorInsertRow(E.numrows, line);
    }
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.error('Opening file:', err.message);
      exit(1);
    }
    return;
  }
  E.dirty = 0;
}

function editorSave() {
  let buf = editorRowsToString();
  try {
    fs.writeFileSync(E.filename, buf);
  } catch (err) {
    editorSetStatusMessage("Can't save! I/O error: " + err.message);
    return 1;
  }
  E.dirty = 0;
  editorSetStatusMessage(buf.length + ' bytes written on disk');
  return 0;
}

let ab = '';

function abAppend(s) {
  ab += s;
}

function abFree() {
  ab = '';
}

function editorRefreshScreen() {
  ab = '';

  abAppend('\x1b[?25l');
  abAppend('\x1b[H');

  for (let y = 0; y < E.screenrows; y++) {
    let filerow = E.rowoff + y;

    if (filerow >= E.numrows) {
      if (E.numrows === 0 && y === Math.floor(E.screenrows / 3)) {
        let welcome = `Kilo editor -- verison ${KILO_VERSION}\x1b[0K\r\n`;
        let padding = Math.floor((E.screencols - welcome.length) / 2);
        if (padding > 0) {
          abAppend('~');
          padding--;
        }
        while (padding-- > 0) abAppend(' ');
        abAppend(welcome);
      } else {
        abAppend('~\x1b[0K\r\n');
      }
      continue;
    }

    let r = E.row[filerow];
    let len = r.rsize - E.coloff;
    let current_color = -1;

    if (len > 0) {
      if (len > E.screencols) len = E.screencols;
      let c = r.render.slice(E.coloff);
      let hl = r.hl;
      let hlOffset = E.coloff;

      for (let j = 0; j < len; j++) {
        let hlType = hl[hlOffset + j];
        if (hlType === HL.NONPRINT) {
          let sym;
          abAppend('\x1b[7m');
          let code = c.charCodeAt(j);
          if (code <= 26)
            sym = String.fromCharCode(0x40 + code);
          else
            sym = '?';
          abAppend(sym);
          abAppend('\x1b[0m');
        } else if (hlType === HL.NORMAL) {
          if (current_color !== -1) {
            abAppend('\x1b[39m');
            current_color = -1;
          }
          abAppend(c[j]);
        } else {
          let color = editorSyntaxToColor(hlType);
          if (color !== current_color) {
            abAppend(`\x1b[${color}m`);
            current_color = color;
          }
          abAppend(c[j]);
        }
      }
    }

    abAppend('\x1b[39m');
    abAppend('\x1b[0K');
    abAppend('\r\n');
  }

  abAppend('\x1b[0K');
  abAppend('\x1b[7m');

  let status = `${E.filename ? E.filename.slice(0, 20) : '[No Name]'} - ${E.numrows} lines${E.dirty ? ' (modified)' : ''}`;
  let rstatus = `${E.rowoff + E.cy + 1}/${E.numrows}`;
  if (status.length > E.screencols) status = status.slice(0, E.screencols);
  abAppend(status);
  let len = status.length;
  while (len < E.screencols) {
    if (E.screencols - len === rstatus.length) {
      abAppend(rstatus);
      break;
    } else {
      abAppend(' ');
      len++;
    }
  }

  abAppend('\x1b[0m\r\n');
  abAppend('\x1b[0K');

  if (E.statusmsg && Date.now() - E.statusmsg_time < 5000) {
    let msglen = E.statusmsg.length;
    abAppend(msglen <= E.screencols ? E.statusmsg : E.statusmsg.slice(0, E.screencols));
  }

  let cx = 1;
  let filerow = E.rowoff + E.cy;
  let row = filerow >= E.numrows ? null : E.row[filerow];
  if (row) {
    for (let j = E.coloff; j < E.cx + E.coloff; j++) {
      if (j < row.chars.length && row.chars[j] === '\t') cx += 7 - ((cx) % 8);
      cx++;
    }
  }

  abAppend(`\x1b[${E.cy + 1};${cx}H`);
  abAppend('\x1b[?25h');

  stdout.write(ab);
}

function editorSetStatusMessage(fmt, ...args) {
  E.statusmsg = fmt.replace(/%d/g, () => String(args.shift())).replace(/%s/g, () => args.shift() || '');
  E.statusmsg_time = Date.now();
}

const KILO_QUERY_LEN = 256;

async function editorFind() {
  let query = '';
  let last_match = -1;
  let find_next = 0;
  let saved_hl_line = -1;
  let saved_hl = null;

  let saved_cx = E.cx, saved_cy = E.cy;
  let saved_coloff = E.coloff, saved_rowoff = E.rowoff;

  function findRestoreHl() {
    if (saved_hl) {
      E.row[saved_hl_line].hl.set(saved_hl);
      saved_hl = null;
    }
  }

  while (true) {
    editorSetStatusMessage(`Search: ${query} (Use ESC/Arrows/Enter)`);
    editorRefreshScreen();

    let c = await editorReadKey();
    if (c === KEY.DEL_KEY || c === KEY.CTRL_H || c === KEY.BACKSPACE) {
      if (query.length > 0) {
        query = query.slice(0, -1);
        last_match = -1;
      }
    } else if (c === KEY.ESC || c === KEY.ENTER) {
      if (c === KEY.ESC) {
        E.cx = saved_cx; E.cy = saved_cy;
        E.coloff = saved_coloff; E.rowoff = saved_rowoff;
      }
      findRestoreHl();
      editorSetStatusMessage('');
      return;
    } else if (c === KEY.ARROW_RIGHT || c === KEY.ARROW_DOWN) {
      find_next = 1;
    } else if (c === KEY.ARROW_LEFT || c === KEY.ARROW_UP) {
      find_next = -1;
    } else if (c >= 32 && c < 127) {
      if (query.length < KILO_QUERY_LEN) {
        query += String.fromCharCode(c);
        last_match = -1;
      }
    }

    if (last_match === -1) find_next = 1;
    if (find_next) {
      let match = null;
      let match_offset = 0;
      let current = last_match;

      for (let i = 0; i < E.numrows; i++) {
        current += find_next;
        if (current === -1) current = E.numrows - 1;
        else if (current === E.numrows) current = 0;
        let idx = E.row[current].render.indexOf(query);
        if (idx !== -1) {
          match = true;
          match_offset = idx;
          break;
        }
      }
      find_next = 0;

      findRestoreHl();

      if (match) {
        let row = E.row[current];
        last_match = current;
        if (row.hl) {
          saved_hl_line = current;
          saved_hl = new Uint8Array(row.hl);
          for (let k = 0; k < query.length; k++) {
            row.hl[match_offset + k] = HL.MATCH;
          }
        }
        E.cy = 0;
        E.cx = match_offset;
        E.rowoff = current;
        E.coloff = 0;
        if (E.cx > E.screencols) {
          let diff = E.cx - E.screencols;
          E.cx -= diff;
          E.coloff += diff;
        }
      }
    }
  }
}

function editorMoveCursor(key) {
  let filerow = E.rowoff + E.cy;
  let filecol = E.coloff + E.cx;
  let row = filerow >= E.numrows ? null : E.row[filerow];

  switch (key) {
    case KEY.ARROW_LEFT:
      if (E.cx === 0) {
        if (E.coloff) {
          E.coloff--;
        } else {
          if (filerow > 0) {
            E.cy--;
            E.cx = E.row[filerow - 1].size;
            if (E.cx > E.screencols - 1) {
              E.coloff = E.cx - E.screencols + 1;
              E.cx = E.screencols - 1;
            }
          }
        }
      } else {
        E.cx--;
      }
      break;
    case KEY.ARROW_RIGHT:
      if (row && filecol < row.size) {
        if (E.cx === E.screencols - 1) {
          E.coloff++;
        } else {
          E.cx++;
        }
      } else if (row && filecol === row.size) {
        E.cx = 0;
        E.coloff = 0;
        if (E.cy === E.screenrows - 1) {
          E.rowoff++;
        } else {
          E.cy++;
        }
      }
      break;
    case KEY.ARROW_UP:
      if (E.cy === 0) {
        if (E.rowoff) E.rowoff--;
      } else {
        E.cy--;
      }
      break;
    case KEY.ARROW_DOWN:
      if (filerow < E.numrows) {
        if (E.cy === E.screenrows - 1) {
          E.rowoff++;
        } else {
          E.cy++;
        }
      }
      break;
  }

  filerow = E.rowoff + E.cy;
  filecol = E.coloff + E.cx;
  row = filerow >= E.numrows ? null : E.row[filerow];
  let rowlen = row ? row.size : 0;
  if (filecol > rowlen) {
    E.cx -= filecol - rowlen;
    if (E.cx < 0) {
      E.coloff += E.cx;
      E.cx = 0;
    }
  }
}

const KILO_QUIT_TIMES = 3;
let quit_times = KILO_QUIT_TIMES;

async function editorProcessKeypress() {
  let c = await editorReadKey();

  switch (c) {
    case KEY.ENTER:
      editorInsertNewline();
      break;
    case KEY.CTRL_C:
      break;
    case KEY.CTRL_Q:
      if (E.dirty && quit_times > 0) {
        editorSetStatusMessage(
          `WARNING!!! File has unsaved changes. Press Ctrl-Q ${quit_times} more times to quit.`
        );
        quit_times--;
        return;
      }
      disableRawMode();
      stdout.write('\x1b[2J\x1b[H');
      exit(0);
      break;
    case KEY.CTRL_S:
      editorSave();
      break;
    case KEY.CTRL_F:
      await editorFind();
      break;
    case KEY.BACKSPACE:
    case KEY.CTRL_H:
    case KEY.DEL_KEY:
      editorDelChar();
      break;
    case KEY.PAGE_UP:
    case KEY.PAGE_DOWN:
      if (c === KEY.PAGE_UP && E.cy !== 0) E.cy = 0;
      else if (c === KEY.PAGE_DOWN && E.cy !== E.screenrows - 1) E.cy = E.screenrows - 1;
      let times = E.screenrows;
      while (times-- > 0) editorMoveCursor(c === KEY.PAGE_UP ? KEY.ARROW_UP : KEY.ARROW_DOWN);
      break;
    case KEY.ARROW_UP:
    case KEY.ARROW_DOWN:
    case KEY.ARROW_LEFT:
    case KEY.ARROW_RIGHT:
      editorMoveCursor(c);
      break;
    case KEY.CTRL_L:
      break;
    case KEY.ESC:
      break;
    default:
      editorInsertChar(c);
      break;
  }

  quit_times = KILO_QUIT_TIMES;
}

function updateWindowSize() {
  if (getWindowSize() === -1) {
    console.error('Unable to query the screen for size (columns / rows)');
    exit(1);
  }
  E.screenrows -= 2;
}

function handleSigWinCh() {
  updateWindowSize();
  if (E.cy > E.screenrows) E.cy = E.screenrows - 1;
  if (E.cx > E.screencols) E.cx = E.screencols - 1;
  editorRefreshScreen();
}

function initEditor() {
  E.cx = 0;
  E.cy = 0;
  E.rowoff = 0;
  E.coloff = 0;
  E.numrows = 0;
  E.row = [];
  E.dirty = 0;
  E.filename = null;
  E.syntax = null;
  updateWindowSize();
}

async function main() {
  if (argv.length !== 3) {
    console.error('Usage: node kilo.js <filename>');
    exit(1);
  }

  initEditor();
  editorSelectSyntaxHighlight(argv[2]);
  editorOpen(argv[2]);
  enableRawMode();

  process.on('SIGWINCH', handleSigWinCh);
  process.on('exit', () => {
    disableRawMode();
    stdout.write('\x1b[2J\x1b[H');
  });
  process.on('SIGINT', () => {
    disableRawMode();
    stdout.write('\x1b[2J\x1b[H');
    exit(0);
  });

  editorSetStatusMessage('HELP: Ctrl-S = save | Ctrl-Q = quit | Ctrl-F = find');

  while (true) {
    editorRefreshScreen();
    await editorProcessKeypress();
  }
}

main().catch((err) => {
  disableRawMode();
  stdout.write('\x1b[2J\x1b[H');
  console.error(err);
  exit(1);
});
