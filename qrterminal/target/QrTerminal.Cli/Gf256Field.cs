// Faithful C# port of rsc.io/qr/gf256
// GF(256) arithmetic with polynomial 0x11d, generator 2
namespace QrTerminal;

internal sealed class Gf256Field
{
    internal readonly byte[] _log = new byte[256]; // log[0] unused
    internal readonly byte[] _exp = new byte[510];

    public Gf256Field(int poly, int alpha)
    {
        int x = 1;
        for (int i = 0; i < 255; i++)
        {
            _exp[i] = (byte)x;
            _exp[i + 255] = (byte)x;
            _log[x] = (byte)i;
            x = GfMul(x, alpha, poly);
        }
        _log[0] = 255;
    }

    private static int GfMul(int x, int y, int poly)
    {
        int z = 0;
        while (x > 0)
        {
            if ((x & 1) != 0) z ^= y;
            x >>= 1;
            y <<= 1;
            if ((y & 0x100) != 0) y ^= poly;
        }
        return z;
    }

    public byte Exp(int e)
    {
        if (e < 0) return 0;
        return _exp[e % 255];
    }

    public int Log(byte x)
    {
        if (x == 0) return -1;
        return _log[x];
    }

    public byte Mul(byte x, byte y)
    {
        if (x == 0 || y == 0) return 0;
        return _exp[_log[x] + _log[y]];
    }

    // Generate Reed-Solomon generator polynomial of degree e
    // Returns (gen, lgen) where lgen[i] = log(gen[i]), 255 if gen[i]==0
    public (byte[] gen, byte[] lgen) GenPoly(int e)
    {
        byte[] p = new byte[e + 1];
        p[e] = 1;
        for (int i = 0; i < e; i++)
        {
            byte c = Exp(i);
            for (int j = 0; j < e; j++)
                p[j] = (byte)(Mul(p[j], c) ^ p[j + 1]);
            p[e] = Mul(p[e], c);
        }
        byte[] lp = new byte[e + 1];
        for (int i = 0; i <= e; i++)
            lp[i] = p[i] == 0 ? (byte)255 : (byte)(byte)Log(p[i]);
        return (p, lp);
    }

    public RsEncoder NewRsEncoder(int c) => new RsEncoder(this, c);
}

internal sealed class RsEncoder
{
    private readonly Gf256Field _f;
    private readonly int _c;
    private readonly byte[] _lgen;

    public RsEncoder(Gf256Field f, int c)
    {
        _f = f;
        _c = c;
        (_, _lgen) = f.GenPoly(c);
    }

    // ECC computes check bytes for data[0..dataLen-1] and writes into check[0..c-1]
    public void ECC(byte[] data, int dataOffset, int dataLen, byte[] check)
    {
        if (_c == 0) return;

        int n = dataLen + _c;
        byte[] p = new byte[n];
        Array.Copy(data, dataOffset, p, 0, dataLen);

        var expArr = _f._exp;
        var logArr = _f._log;

        for (int i = 0; i < dataLen; i++)
        {
            byte c = p[i];
            if (c == 0) continue;
            int lc = logArr[c];
            for (int j = 0; j < _c; j++)
            {
                byte lg = _lgen[j + 1]; // lgen[1..] skips leading coeff
                if (lg != 255)
                    p[i + 1 + j] ^= expArr[lc + lg];
            }
        }
        Array.Copy(p, dataLen, check, 0, _c);
    }
}
