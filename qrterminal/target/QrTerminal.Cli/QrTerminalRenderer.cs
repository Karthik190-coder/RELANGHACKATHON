// Faithful C# port of github.com/mdp/qrterminal/v3 qrterminal.go rendering logic
namespace QrTerminal;

internal static class QrTerminalRenderer
{
    // ANSI escape code constants — exactly matching Go source
    public const string White = "\x1b[47m  \x1b[0m";
    public const string Black = "\x1b[40m  \x1b[0m";

    // Half-block Unicode characters
    public const string BlackBlack = " ";
    public const string BlackWhite = "▄";
    public const string WhiteBlack = "▀";
    public const string WhiteWhite = "█";

    public const int QuietZone = 4;

    // Sixel constants (not used in test mode but kept for completeness)
    public const string SixelBegin = "\x1bPq\n#0;2;0;0;0#1;2;100;100;100\n";
    public const string SixelEnd = "\x1b\\";
    public const int SixelBlockSize = 12;

    /// <summary>Port of stringRepeat — returns "" for count &lt;= 0</summary>
    public static string StringRepeat(string s, int count)
    {
        if (count <= 0) return "";
        if (count == 1) return s;
        var sb = new System.Text.StringBuilder(s.Length * count);
        for (int i = 0; i < count; i++) sb.Append(s);
        return sb.ToString();
    }

    /// <summary>Port of writeFullBlocks</summary>
    public static void WriteFullBlocks(System.IO.TextWriter w, QrCode code, string whiteChar, string blackChar, int quietZone)
    {
        // top border
        string topLine = StringRepeat(whiteChar, code.Size + quietZone * 2) + "\n";
        w.Write(StringRepeat(topLine, quietZone));

        for (int i = 0; i <= code.Size; i++)
        {
            w.Write(StringRepeat(whiteChar, quietZone)); // left border
            for (int j = 0; j <= code.Size; j++)
            {
                w.Write(code.Black(j, i) ? blackChar : whiteChar);
            }
            w.Write(StringRepeat(whiteChar, quietZone - 1) + "\n"); // right border
        }

        // bottom border
        w.Write(StringRepeat(StringRepeat(whiteChar, code.Size + quietZone * 2) + "\n", quietZone - 1));
    }

    /// <summary>Port of writeHalfBlocks</summary>
    public static void WriteHalfBlocks(System.IO.TextWriter w, QrCode code, 
        string ww, string bb, string wb, string bw, int quietZone)
    {
        // top border
        if (quietZone % 2 != 0)
        {
            w.Write(StringRepeat(bw, code.Size + quietZone * 2) + "\n");
            w.Write(StringRepeat(StringRepeat(ww, code.Size + quietZone * 2) + "\n", quietZone / 2));
        }
        else
        {
            w.Write(StringRepeat(StringRepeat(ww, code.Size + quietZone * 2) + "\n", quietZone / 2));
        }

        for (int i = 0; i <= code.Size; i += 2)
        {
            w.Write(StringRepeat(ww, quietZone)); // left border
            for (int j = 0; j <= code.Size; j++)
            {
                bool nextBlack = false;
                if (i + 1 < code.Size)
                    nextBlack = code.Black(j, i + 1);
                bool currBlack = code.Black(j, i);
                if (currBlack && nextBlack)
                    w.Write(bb);
                else if (currBlack && !nextBlack)
                    w.Write(bw);
                else if (!currBlack && !nextBlack)
                    w.Write(ww);
                else
                    w.Write(wb);
            }
            w.Write(StringRepeat(ww, quietZone - 1) + "\n"); // right border
        }

        // bottom border
        if (quietZone % 2 == 0)
        {
            w.Write(StringRepeat(StringRepeat(ww, code.Size + quietZone * 2) + "\n", quietZone / 2 - 1));
            w.Write(StringRepeat(wb, code.Size + quietZone * 2) + "\n");
        }
        else
        {
            w.Write(StringRepeat(StringRepeat(ww, code.Size + quietZone * 2) + "\n", quietZone / 2));
        }
    }

    /// <summary>Port of GenerateWithConfig</summary>
    public static void GenerateWithConfig(string text, QrTerminalConfig config)
    {
        if (config.QuietZone < 1) config.QuietZone = 1;

        var code = QrEncoder.Encode(text, config.Level);
        if (code == null) return; // text too long

        // Set default characters if not provided
        string blackChar      = string.IsNullOrEmpty(config.BlackChar)      ? BlackBlack : config.BlackChar;
        string whiteBlackChar = string.IsNullOrEmpty(config.WhiteBlackChar) ? WhiteBlack : config.WhiteBlackChar;
        string whiteChar      = string.IsNullOrEmpty(config.WhiteChar)      ? WhiteWhite : config.WhiteChar;
        string blackWhiteChar = string.IsNullOrEmpty(config.BlackWhiteChar) ? BlackWhite : config.BlackWhiteChar;

        if (config.HalfBlocks)
        {
            WriteHalfBlocks(config.Writer, code, whiteChar, blackChar, whiteBlackChar, blackWhiteChar, config.QuietZone);
        }
        else
        {
            WriteFullBlocks(config.Writer, code, whiteChar, blackChar, config.QuietZone);
        }
    }

    /// <summary>Port of Generate — uses ANSI color blocks</summary>
    public static void Generate(string text, QrLevel level, System.IO.TextWriter w)
    {
        var config = new QrTerminalConfig
        {
            Level     = level,
            Writer    = w,
            BlackChar = Black,
            WhiteChar = White,
            QuietZone = QuietZone,
        };
        GenerateWithConfig(text, config);
    }

    /// <summary>Port of GenerateHalfBlock</summary>
    public static void GenerateHalfBlock(string text, QrLevel level, System.IO.TextWriter w)
    {
        var config = new QrTerminalConfig
        {
            Level          = level,
            Writer         = w,
            HalfBlocks     = true,
            BlackChar      = BlackBlack,
            WhiteBlackChar = WhiteBlack,
            WhiteChar      = WhiteWhite,
            BlackWhiteChar = BlackWhite,
            QuietZone      = QuietZone,
        };
        GenerateWithConfig(text, config);
    }
}

internal sealed class QrTerminalConfig
{
    public QrLevel Level { get; set; }
    public System.IO.TextWriter Writer { get; set; } = System.Console.Out;
    public bool HalfBlocks { get; set; }
    public string BlackChar { get; set; } = "";
    public string BlackWhiteChar { get; set; } = "";
    public string WhiteChar { get; set; } = "";
    public string WhiteBlackChar { get; set; } = "";
    public int QuietZone { get; set; } = QrTerminalRenderer.QuietZone;
}
