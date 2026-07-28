// Faithful C# port of rsc.io/qr top-level Encode function
// Encoding mode selection: Num > Alpha > String (byte)
namespace QrTerminal;

internal static class QrEncoder
{
    // Alphanumeric character set
    private const string Alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";

    // ---- Encoding mode checks ----

    private static bool IsNumeric(string s)
    {
        foreach (char c in s)
            if (c < '0' || c > '9') return false;
        return true;
    }

    private static bool IsAlpha(string s)
    {
        foreach (char c in s)
            if (Alphabet.IndexOf(c) < 0) return false;
        return true;
    }

    private static int SizeClass(int version)
    {
        if (version <= 9) return 0;
        if (version <= 26) return 1;
        return 2;
    }

    // ---- Bits needed per mode ----

    private static readonly int[] NumLen   = { 10, 12, 14 };
    private static readonly int[] AlphaLen = { 9, 11, 13 };
    private static readonly int[] StrLen   = { 8, 16, 16 };

    private static int NumBits(string s, int version)
        => 4 + NumLen[SizeClass(version)] + (10 * s.Length + 2) / 3;

    private static int AlphaBits(string s, int version)
        => 4 + AlphaLen[SizeClass(version)] + (11 * s.Length + 1) / 2;

    private static int StringBits(string s, int version)
    {
        // Byte-length in ISO-8859-1 interpretation (go uses len(s) which is utf-8 byte length)
        // We need the raw UTF-8 byte count to match Go's String encoding
        byte[] utf8 = System.Text.Encoding.UTF8.GetBytes(s);
        return 4 + StrLen[SizeClass(version)] + 8 * utf8.Length;
    }

    // ---- Encoding write ----

    private static void EncodeNum(Bits b, string s, int version)
    {
        b.Write(1, 4);
        b.Write((uint)s.Length, NumLen[SizeClass(version)]);
        int i = 0;
        for (; i + 3 <= s.Length; i += 3)
        {
            uint w = (uint)(s[i] - '0') * 100 + (uint)(s[i + 1] - '0') * 10 + (uint)(s[i + 2] - '0');
            b.Write(w, 10);
        }
        switch (s.Length - i)
        {
            case 1: b.Write((uint)(s[i] - '0'), 4); break;
            case 2: b.Write((uint)(s[i] - '0') * 10 + (uint)(s[i + 1] - '0'), 7); break;
        }
    }

    private static void EncodeAlpha(Bits b, string s, int version)
    {
        b.Write(2, 4);
        b.Write((uint)s.Length, AlphaLen[SizeClass(version)]);
        int i = 0;
        for (; i + 2 <= s.Length; i += 2)
        {
            uint w = (uint)Alphabet.IndexOf(s[i]) * 45 + (uint)Alphabet.IndexOf(s[i + 1]);
            b.Write(w, 11);
        }
        if (i < s.Length)
            b.Write((uint)Alphabet.IndexOf(s[i]), 6);
    }

    private static void EncodeString(Bits b, string s, int version)
    {
        // Go's String encoding uses raw bytes (the string is treated as []byte)
        byte[] utf8 = System.Text.Encoding.UTF8.GetBytes(s);
        b.Write(4, 4);
        b.Write((uint)utf8.Length, StrLen[SizeClass(version)]);
        foreach (byte bb in utf8)
            b.Write(bb, 8);
    }

    // ---- Main Encode ----

    /// <summary>
    /// Encodes text at the given level. Returns null if text is too long.
    /// Faithfully ports rsc.io/qr Encode(): picks smallest encoding mode,
    /// picks smallest version that fits, builds plan with mask=0, encodes.
    /// </summary>
    public static QrCode? Encode(string text, QrLevel level)
    {
        // Pick encoding mode (Numeric > Alpha > String)
        int encMode; // 0=num, 1=alpha, 2=string
        if (IsNumeric(text))      encMode = 0;
        else if (IsAlpha(text))   encMode = 1;
        else                       encMode = 2;

        // Pick smallest version
        int version = -1;
        for (int v = QrCoding.MinVersion; v <= QrCoding.MaxVersion; v++)
        {
            int bitsNeeded;
            switch (encMode)
            {
                case 0: bitsNeeded = NumBits(text, v);    break;
                case 1: bitsNeeded = AlphaBits(text, v);  break;
                default: bitsNeeded = StringBits(text, v); break;
            }
            if (bitsNeeded <= VersionTable.DataBytes(v, level) * 8)
            {
                version = v;
                break;
            }
        }
        if (version < 0) return null; // too long

        // Build plan with mask=0 (rsc.io/qr always uses mask 0)
        var p = QrCoding.NewPlan(version, level, 0);

        // Encode bits
        var b = new Bits();
        switch (encMode)
        {
            case 0: EncodeNum(b, text, version);    break;
            case 1: EncodeAlpha(b, text, version);  break;
            default: EncodeString(b, text, version); break;
        }

        return QrCoding.EncodePlan(p, b);
    }
}
