// Wren Lexer / Scanner

const TokenType = {
  TOKEN_LEFT_PAREN: "TOKEN_LEFT_PAREN",
  TOKEN_RIGHT_PAREN: "TOKEN_RIGHT_PAREN",
  TOKEN_LEFT_BRACKET: "TOKEN_LEFT_BRACKET",
  TOKEN_RIGHT_BRACKET: "TOKEN_RIGHT_BRACKET",
  TOKEN_LEFT_BRACE: "TOKEN_LEFT_BRACE",
  TOKEN_RIGHT_BRACE: "TOKEN_RIGHT_BRACE",
  TOKEN_COLON: "TOKEN_COLON",
  TOKEN_DOT: "TOKEN_DOT",
  TOKEN_DOTDOT: "TOKEN_DOTDOT",
  TOKEN_DOTDOTDOT: "TOKEN_DOTDOTDOT",
  TOKEN_COMMA: "TOKEN_COMMA",
  TOKEN_STAR: "TOKEN_STAR",
  TOKEN_SLASH: "TOKEN_SLASH",
  TOKEN_PERCENT: "TOKEN_PERCENT",
  TOKEN_PLUS: "TOKEN_PLUS",
  TOKEN_MINUS: "TOKEN_MINUS",
  TOKEN_PIPE: "TOKEN_PIPE",
  TOKEN_PIPEPIPE: "TOKEN_PIPEPIPE",
  TOKEN_CARET: "TOKEN_CARET",
  TOKEN_AMP: "TOKEN_AMP",
  TOKEN_AMPAMP: "TOKEN_AMPAMP",
  TOKEN_BANG: "TOKEN_BANG",
  TOKEN_BANGEQUAL: "TOKEN_BANGEQUAL",
  TOKEN_EQUAL: "TOKEN_EQUAL",
  TOKEN_EQUALEQUAL: "TOKEN_EQUALEQUAL",
  TOKEN_GREATER: "TOKEN_GREATER",
  TOKEN_GREATEREQUAL: "TOKEN_GREATEREQUAL",
  TOKEN_LESS: "TOKEN_LESS",
  TOKEN_LESSEQUAL: "TOKEN_LESSEQUAL",
  TOKEN_TILDE: "TOKEN_TILDE",
  TOKEN_QUESTION: "TOKEN_QUESTION",
  TOKEN_SHL: "TOKEN_SHL",
  TOKEN_SHR: "TOKEN_SHR",

  TOKEN_NUMBER: "TOKEN_NUMBER",
  TOKEN_STRING: "TOKEN_STRING",
  TOKEN_INTERPOLATION: "TOKEN_INTERPOLATION",
  TOKEN_NAME: "TOKEN_NAME",
  TOKEN_FIELD: "TOKEN_FIELD",
  TOKEN_STATIC_FIELD: "TOKEN_STATIC_FIELD",

  // Keywords
  TOKEN_BREAK: "TOKEN_BREAK",
  TOKEN_CLASS: "TOKEN_CLASS",
  TOKEN_CONSTRUCT: "TOKEN_CONSTRUCT",
  TOKEN_CONTINUE: "TOKEN_CONTINUE",
  TOKEN_ELSE: "TOKEN_ELSE",
  TOKEN_FALSE: "TOKEN_FALSE",
  TOKEN_FOR: "TOKEN_FOR",
  TOKEN_FOREIGN: "TOKEN_FOREIGN",
  TOKEN_IF: "TOKEN_IF",
  TOKEN_IMPORT: "TOKEN_IMPORT",
  TOKEN_IN: "TOKEN_IN",
  TOKEN_IS: "TOKEN_IS",
  TOKEN_NULL: "TOKEN_NULL",
  TOKEN_RETURN: "TOKEN_RETURN",
  TOKEN_STATIC: "TOKEN_STATIC",
  TOKEN_SUPER: "TOKEN_SUPER",
  TOKEN_THIS: "TOKEN_THIS",
  TOKEN_TRUE: "TOKEN_TRUE",
  TOKEN_VAR: "TOKEN_VAR",
  TOKEN_WHILE: "TOKEN_WHILE",

  TOKEN_LINE: "TOKEN_LINE",
  TOKEN_ERROR: "TOKEN_ERROR",
  TOKEN_EOF: "TOKEN_EOF"
};

const KEYWORDS = {
  "break": TokenType.TOKEN_BREAK,
  "class": TokenType.TOKEN_CLASS,
  "construct": TokenType.TOKEN_CONSTRUCT,
  "continue": TokenType.TOKEN_CONTINUE,
  "else": TokenType.TOKEN_ELSE,
  "false": TokenType.TOKEN_FALSE,
  "for": TokenType.TOKEN_FOR,
  "foreign": TokenType.TOKEN_FOREIGN,
  "if": TokenType.TOKEN_IF,
  "import": TokenType.TOKEN_IMPORT,
  "in": TokenType.TOKEN_IN,
  "is": TokenType.TOKEN_IS,
  "null": TokenType.TOKEN_NULL,
  "return": TokenType.TOKEN_RETURN,
  "static": TokenType.TOKEN_STATIC,
  "super": TokenType.TOKEN_SUPER,
  "this": TokenType.TOKEN_THIS,
  "true": TokenType.TOKEN_TRUE,
  "var": TokenType.TOKEN_VAR,
  "while": TokenType.TOKEN_WHILE
};

class Token {
  constructor(type, text, value, line) {
    this.type = type;
    this.text = text;
    this.value = value;
    this.line = line;
  }
}

class Lexer {
  constructor(source) {
    this.source = source;
    this.start = 0;
    this.current = 0;
    this.line = 1;
    this.numParens = 0;
    this.parens = []; // stack of parens for string interpolation nest levels
  }

  scanToken() {
    this.skipWhitespaceAndComments();
    this.start = this.current;

    if (this.isAtEnd()) {
      return this.makeToken(TokenType.TOKEN_EOF);
    }

    const c = this.advance();

    if (c === '\n') {
      this.line++;
      return this.makeToken(TokenType.TOKEN_LINE);
    }

    if (this.isAlpha(c) || c === '_') {
      return this.identifier();
    }

    if (this.isDigit(c)) {
      return this.number();
    }

    switch (c) {
      case '(':
        if (this.parens.length > 0) {
          this.parens[this.parens.length - 1]++;
        }
        return this.makeToken(TokenType.TOKEN_LEFT_PAREN);
      case ')':
        if (this.parens.length > 0) {
          this.parens[this.parens.length - 1]--;
          if (this.parens[this.parens.length - 1] === -1) {
            this.parens.pop();
            return this.readString(); // Resume parsing interpolated string
          }
        }
        return this.makeToken(TokenType.TOKEN_RIGHT_PAREN);
      case '[': return this.makeToken(TokenType.TOKEN_LEFT_BRACKET);
      case ']': return this.makeToken(TokenType.TOKEN_RIGHT_BRACKET);
      case '{': return this.makeToken(TokenType.TOKEN_LEFT_BRACE);
      case '}': return this.makeToken(TokenType.TOKEN_RIGHT_BRACE);
      case ':': return this.makeToken(TokenType.TOKEN_COLON);
      case ',': return this.makeToken(TokenType.TOKEN_COMMA);
      case '*': return this.makeToken(TokenType.TOKEN_STAR);
      case '%': return this.makeToken(TokenType.TOKEN_PERCENT);
      case '+': return this.makeToken(TokenType.TOKEN_PLUS);
      case '-': return this.makeToken(TokenType.TOKEN_MINUS);
      case '~': return this.makeToken(TokenType.TOKEN_TILDE);
      case '?': return this.makeToken(TokenType.TOKEN_QUESTION);
      case '^': return this.makeToken(TokenType.TOKEN_CARET);

      case '|':
        return this.makeToken(this.match('|') ? TokenType.TOKEN_PIPEPIPE : TokenType.TOKEN_PIPE);
      case '&':
        return this.makeToken(this.match('&') ? TokenType.TOKEN_AMPAMP : TokenType.TOKEN_AMP);

      case '=':
        return this.makeToken(this.match('=') ? TokenType.TOKEN_EQUALEQUAL : TokenType.TOKEN_EQUAL);
      case '!':
        return this.makeToken(this.match('=') ? TokenType.TOKEN_BANGEQUAL : TokenType.TOKEN_BANG);
      case '<':
        if (this.match('=')) return this.makeToken(TokenType.TOKEN_LESSEQUAL);
        if (this.match('<')) return this.makeToken(TokenType.TOKEN_SHL);
        return this.makeToken(TokenType.TOKEN_LESS);
      case '>':
        if (this.match('=')) return this.makeToken(TokenType.TOKEN_GREATEREQUAL);
        if (this.match('>')) return this.makeToken(TokenType.TOKEN_SHR);
        return this.makeToken(TokenType.TOKEN_GREATER);

      case '.':
        if (this.match('.')) {
          if (this.match('.')) {
            return this.makeToken(TokenType.TOKEN_DOTDOTDOT);
          }
          return this.makeToken(TokenType.TOKEN_DOTDOT);
        }
        return this.makeToken(TokenType.TOKEN_DOT);

      case '/':
        return this.makeToken(TokenType.TOKEN_SLASH);

      case '"':
        if (this.peek() === '"' && this.peekNext() === '"') {
          this.advance();
          this.advance();
          return this.rawString();
        }
        return this.readString();
    }

    return this.errorToken(`Unexpected character '${c}'.`);
  }

  isAtEnd() {
    return this.current >= this.source.length;
  }

  advance() {
    return this.source[this.current++];
  }

  peek() {
    if (this.isAtEnd()) return '\0';
    return this.source[this.current];
  }

  peekNext() {
    if (this.current + 1 >= this.source.length) return '\0';
    return this.source[this.current + 1];
  }

  match(expected) {
    if (this.isAtEnd()) return false;
    if (this.source[this.current] !== expected) return false;
    this.current++;
    return true;
  }

  makeToken(type, value = null) {
    return new Token(type, this.source.substring(this.start, this.current), value, this.line);
  }

  errorToken(message) {
    return new Token(TokenType.TOKEN_ERROR, message, null, this.line);
  }

  skipWhitespaceAndComments() {
    while (!this.isAtEnd()) {
      const c = this.peek();
      switch (c) {
        case ' ':
        case '\r':
        case '\t':
          this.advance();
          break;
        case '/':
          if (this.peekNext() === '/') {
            // Line comment
            while (this.peek() !== '\n' && !this.isAtEnd()) {
              this.advance();
            }
          } else if (this.peekNext() === '*') {
            // Block comment (nestable)
            this.advance();
            this.advance();
            let nesting = 1;
            while (nesting > 0 && !this.isAtEnd()) {
              if (this.peek() === '/' && this.peekNext() === '*') {
                this.advance();
                this.advance();
                nesting++;
              } else if (this.peek() === '*' && this.peekNext() === '/') {
                this.advance();
                this.advance();
                nesting--;
              } else {
                if (this.peek() === '\n') this.line++;
                this.advance();
              }
            }
          } else {
            return;
          }
          break;
        default:
          return;
      }
    }
  }

  isAlpha(c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
  }

  isDigit(c) {
    return c >= '0' && c <= '9';
  }

  isHexDigit(c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
  }

  identifier() {
    while (this.isAlpha(this.peek()) || this.isDigit(this.peek()) || this.peek() === '_') {
      this.advance();
    }

    const text = this.source.substring(this.start, this.current);
    
    if (text.startsWith("__")) {
      return this.makeToken(TokenType.TOKEN_STATIC_FIELD);
    }
    if (text.startsWith("_")) {
      return this.makeToken(TokenType.TOKEN_FIELD);
    }

    // Keywords must be explicit table entries. A plain-object lookup turns
    // identifiers such as `toString` into inherited JavaScript properties,
    // which corrupts otherwise valid Wren member expressions.
    const type = Object.prototype.hasOwnProperty.call(KEYWORDS, text)
      ? KEYWORDS[text]
      : TokenType.TOKEN_NAME;
    return this.makeToken(type);
  }

  number() {
    if (this.source[this.start] === '0' && (this.peek() === 'x' || this.peek() === 'X')) {
      this.advance(); // 'x'
      while (this.isHexDigit(this.peek())) this.advance();
      const val = parseInt(this.source.substring(this.start + 2, this.current), 16);
      return this.makeToken(TokenType.TOKEN_NUMBER, val);
    }

    if (this.source[this.start] === '0' && (this.peek() === 'b' || this.peek() === 'B')) {
      this.advance(); // 'b'
      while (this.peek() === '0' || this.peek() === '1') this.advance();
      const val = parseInt(this.source.substring(this.start + 2, this.current), 2);
      return this.makeToken(TokenType.TOKEN_NUMBER, val);
    }

    while (this.isDigit(this.peek())) this.advance();

    if (this.peek() === '.' && this.isDigit(this.peekNext())) {
      this.advance(); // '.'
      while (this.isDigit(this.peek())) this.advance();
    }

    // Scientific notation
    if (this.peek() === 'e' || this.peek() === 'E') {
      this.advance();
      if (this.peek() === '+' || this.peek() === '-') this.advance();
      while (this.isDigit(this.peek())) this.advance();
    }

    const val = parseFloat(this.source.substring(this.start, this.current));
    return this.makeToken(TokenType.TOKEN_NUMBER, val);
  }

  readString() {
    let stringVal = "";

    while (!this.isAtEnd()) {
      const c = this.advance();

      if (c === '"') {
        return this.makeToken(TokenType.TOKEN_STRING, stringVal);
      }

      if (c === '\n') {
        this.line++;
      }

      if (c === '%') {
        if (this.peek() === '(') {
          this.advance(); // '('
          this.parens.push(0);
          return this.makeToken(TokenType.TOKEN_INTERPOLATION, stringVal);
        }
      }

      if (c === '\\') {
        switch (this.advance()) {
          case '"': stringVal += '"'; break;
          case '\\': stringVal += '\\'; break;
          case '%': stringVal += '%'; break;
          case '0': stringVal += '\0'; break;
          case 'a': stringVal += '\x07'; break;
          case 'b': stringVal += '\b'; break;
          case 'f': stringVal += '\f'; break;
          case 'n': stringVal += '\n'; break;
          case 'r': stringVal += '\r'; break;
          case 't': stringVal += '\t'; break;
          case 'v': stringVal += '\v'; break;
          case 'x': {
            const hex = this.advance() + this.advance();
            stringVal += String.fromCharCode(parseInt(hex, 16));
            break;
          }
          case 'u': {
            const hex = this.advance() + this.advance() + this.advance() + this.advance();
            stringVal += String.fromCharCode(parseInt(hex, 16));
            break;
          }
          case 'U': {
            const hex = this.advance() + this.advance() + this.advance() + this.advance() +
                        this.advance() + this.advance() + this.advance() + this.advance();
            stringVal += String.fromCodePoint(parseInt(hex, 16));
            break;
          }
          default:
            return this.errorToken("Invalid escape sequence.");
        }
      } else {
        stringVal += c;
      }
    }

    return this.errorToken("Unterminated string.");
  }

  rawString() {
    let stringVal = "";

    // Strip leading newline if present
    if (this.peek() === '\n') {
      this.advance();
      this.line++;
    } else if (this.peek() === '\r' && this.peekNext() === '\n') {
      this.advance();
      this.advance();
      this.line++;
    }

    while (!this.isAtEnd()) {
      if (this.peek() === '"' && this.peekNext() === '"' && this.source[this.current + 2] === '"') {
        this.advance();
        this.advance();
        this.advance();
        return this.makeToken(TokenType.TOKEN_STRING, stringVal);
      }

      const c = this.advance();
      if (c === '\n') this.line++;
      stringVal += c;
    }

    return this.errorToken("Unterminated raw string.");
  }
}

module.exports = {
  TokenType,
  Token,
  Lexer
};
