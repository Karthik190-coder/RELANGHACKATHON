// Faithful C# port of rsc.io/qr/coding
// Pixel roles, bit packing, encoding modes, version table, plan building, mask
namespace QrTerminal;

// ---- Pixel ----------------------------------------------------------------

[Flags]
internal enum PixelFlags : uint
{
    None   = 0,
    Black  = 1,
    Invert = 2,
}

internal enum PixelRole : uint
{
    None      = 0,
    Position  = 1,
    Alignment = 2,
    Timing    = 3,
    Format    = 4,
    PVersion  = 5,
    Unused    = 6,
    Data      = 7,
    Check     = 8,
    Extra     = 9,
}

// A Pixel encodes role (bits 2-5), flags (bits 0-1), offset (bits 6+)
// matching Go's Pixel uint32 layout exactly.
internal readonly struct Pixel
{
    private readonly uint _v;
    public Pixel(uint v) => _v = v;

    public PixelRole Role() => (PixelRole)((_v >> 2) & 15);
    public uint Offset() => _v >> 6;
    public bool IsBlack() => (_v & (uint)PixelFlags.Black) != 0;

    public static Pixel ForRole(PixelRole r) => new Pixel((uint)r << 2);
    public static Pixel OffsetPixel(uint o) => new Pixel(o << 6);

    public Pixel WithBlack() => new Pixel(_v | (uint)PixelFlags.Black);
    public Pixel XorBlackInvert() => new Pixel(_v ^ ((uint)PixelFlags.Black | (uint)PixelFlags.Invert));
    public Pixel Or(Pixel other) => new Pixel(_v | other._v);
    public Pixel Xor(Pixel other) => new Pixel(_v ^ other._v);

    public static readonly Pixel Zero = new Pixel(0);
}

// ---- Level ----------------------------------------------------------------

internal enum QrLevel
{
    L = 0,
    M = 1,
    Q = 2,
    H = 3,
}

// ---- Bits -----------------------------------------------------------------

internal sealed class Bits
{
    private byte[] _b = Array.Empty<byte>();
    private int _nbit;

    public int BitCount => _nbit;

    public void Reset()
    {
        Array.Clear(_b, 0, _b.Length);
        _b = Array.Empty<byte>();
        _nbit = 0;
    }

    public byte[] Bytes()
    {
        if (_nbit % 8 != 0) throw new InvalidOperationException("fractional byte");
        // Return exactly the used bytes (like Go's b.b slice)
        return _b[0..(_nbit / 8)];
    }

    public void Append(byte[] p)
    {
        if (_nbit % 8 != 0) throw new InvalidOperationException("fractional byte");
        int usedBytes = _nbit / 8;
        if (_b.Length < usedBytes + p.Length)
        {
            var nb = new byte[usedBytes + p.Length];
            Array.Copy(_b, nb, usedBytes);
            _b = nb;
        }
        Array.Copy(p, 0, _b, usedBytes, p.Length);
        _nbit += 8 * p.Length;
    }

    // Write v using nbit bits (most significant first), matching Go's Bits.Write exactly
    public void Write(uint v, int nbit)
    {
        while (nbit > 0)
        {
            int n = nbit;
            if (n > 8) n = 8;
            if (_nbit % 8 == 0)
            {
                // Grow by one byte
                if (_b.Length <= _nbit / 8)
                {
                    var nb = new byte[Math.Max(_b.Length * 2, _nbit / 8 + 8)];
                    Array.Copy(_b, nb, _b.Length);
                    _b = nb;
                }
                // _b[_nbit/8] is already 0 from allocation
            }
            else
            {
                int m = -_nbit & 7;
                if (n > m) n = m;
            }
            _nbit += n;
            uint sh = (uint)(nbit - n);
            int byteIdx = _nbit / 8 - (_nbit % 8 == 0 ? 1 : 0);
            // When _nbit%8==0 after increment, last byte is _nbit/8-1
            // When _nbit%8!=0, last byte is _nbit/8
            byteIdx = (_nbit - 1) / 8;
            _b[byteIdx] |= (byte)((v >> (int)sh) << (-_nbit & 7));
            v -= (v >> (int)sh) << (int)sh;
            nbit -= n;
        }
    }

    public void Pad(int n)
    {
        if (n < 0) throw new InvalidOperationException("qr: invalid pad size");
        if (n <= 4)
        {
            Write(0, n);
        }
        else
        {
            Write(0, 4);
            n -= 4;
            n -= (-_nbit & 7);
            Write(0, -_nbit & 7);
            int pad = n / 8;
            for (int i = 0; i < pad; i += 2)
            {
                Write(0xec, 8);
                if (i + 1 >= pad) break;
                Write(0x11, 8);
            }
        }
    }

    public void AddCheckBytes(int version, QrLevel level)
    {
        int nd = VersionTable.DataBytes(version, level);
        if (_nbit < nd * 8) Pad(nd * 8 - _nbit);
        if (_nbit != nd * 8) throw new InvalidOperationException("qr: too much data");

        // Snapshot data bytes BEFORE appending check bytes (Go: dat := b.Bytes())
        byte[] dat = new byte[nd];
        Array.Copy(_b, 0, dat, 0, nd);

        var vt = VersionTable.Vtab[version];
        var lev = vt.Levels[(int)level];
        int db = nd / lev.NBlock;
        int extra = nd % lev.NBlock;
        byte[] chk = new byte[lev.Check];
        var rs = QrCoding.Field.NewRsEncoder(lev.Check);
        int dataOff = 0;
        for (int i = 0; i < lev.NBlock; i++)
        {
            // Go: if i == lev.nblock-extra { db++ } — permanent increment
            if (i == lev.NBlock - extra) db++;
            rs.ECC(dat, dataOff, db, chk);
            Append(chk);
            dataOff += db;
        }

        if (Bytes().Length != vt.Bytes)
            throw new InvalidOperationException("qr: internal error");
    }
}

// ---- Version table --------------------------------------------------------

internal struct LevelInfo
{
    public int NBlock;
    public int Check;
}

internal struct VersionInfo
{
    public int Apos;
    public int Astride;
    public int Bytes;
    public int Pattern;
    public LevelInfo[] Levels; // [4]: L M Q H
}

internal static class VersionTable
{
    public static readonly VersionInfo[] Vtab = BuildVtab();

    private static VersionInfo[] BuildVtab()
    {
        // Directly ported from rsc.io/qr/coding/qr.go vtab literal
        // {apos, astride, bytes, pattern, [{nblock,check}x4]}
        return new VersionInfo[]
        {
            /* 0 placeholder */ new VersionInfo(),
            new VersionInfo { Apos=100, Astride=100, Bytes=26,   Pattern=0x0,     Levels=L(1,7,   1,10,  1,13,  1,17)  },// 1
            new VersionInfo { Apos=16,  Astride=100, Bytes=44,   Pattern=0x0,     Levels=L(1,10,  1,16,  1,22,  1,28)  },// 2
            new VersionInfo { Apos=20,  Astride=100, Bytes=70,   Pattern=0x0,     Levels=L(1,15,  1,26,  2,18,  2,22)  },// 3
            new VersionInfo { Apos=24,  Astride=100, Bytes=100,  Pattern=0x0,     Levels=L(1,20,  2,18,  2,26,  4,16)  },// 4
            new VersionInfo { Apos=28,  Astride=100, Bytes=134,  Pattern=0x0,     Levels=L(1,26,  2,24,  4,18,  4,22)  },// 5
            new VersionInfo { Apos=32,  Astride=100, Bytes=172,  Pattern=0x0,     Levels=L(2,18,  4,16,  4,24,  4,28)  },// 6
            new VersionInfo { Apos=20,  Astride=16,  Bytes=196,  Pattern=0x7c94,  Levels=L(2,20,  4,18,  6,18,  5,26)  },// 7
            new VersionInfo { Apos=22,  Astride=18,  Bytes=242,  Pattern=0x85bc,  Levels=L(2,24,  4,22,  6,22,  6,26)  },// 8
            new VersionInfo { Apos=24,  Astride=20,  Bytes=292,  Pattern=0x9a99,  Levels=L(2,30,  5,22,  8,20,  8,24)  },// 9
            new VersionInfo { Apos=26,  Astride=22,  Bytes=346,  Pattern=0xa4d3,  Levels=L(4,18,  5,26,  8,24,  8,28)  },// 10
            new VersionInfo { Apos=28,  Astride=24,  Bytes=404,  Pattern=0xbbf6,  Levels=L(4,20,  5,30,  8,28,  11,24) },// 11
            new VersionInfo { Apos=30,  Astride=26,  Bytes=466,  Pattern=0xc762,  Levels=L(4,24,  8,22,  10,26, 11,28) },// 12
            new VersionInfo { Apos=32,  Astride=28,  Bytes=532,  Pattern=0xd847,  Levels=L(4,26,  9,22,  12,24, 16,22) },// 13
            new VersionInfo { Apos=24,  Astride=20,  Bytes=581,  Pattern=0xe60d,  Levels=L(4,30,  9,24,  16,20, 16,24) },// 14
            new VersionInfo { Apos=24,  Astride=22,  Bytes=655,  Pattern=0xf928,  Levels=L(6,22,  10,24, 12,30, 18,24) },// 15
            new VersionInfo { Apos=24,  Astride=24,  Bytes=733,  Pattern=0x10b78, Levels=L(6,24,  10,28, 17,24, 16,30) },// 16
            new VersionInfo { Apos=28,  Astride=24,  Bytes=815,  Pattern=0x1145d, Levels=L(6,28,  11,28, 16,28, 19,28) },// 17
            new VersionInfo { Apos=28,  Astride=26,  Bytes=901,  Pattern=0x12a17, Levels=L(6,30,  13,26, 18,28, 21,28) },// 18
            new VersionInfo { Apos=28,  Astride=28,  Bytes=991,  Pattern=0x13532, Levels=L(7,28,  14,26, 21,26, 25,26) },// 19
            new VersionInfo { Apos=32,  Astride=28,  Bytes=1085, Pattern=0x149a6, Levels=L(8,28,  16,26, 20,30, 25,28) },// 20
            new VersionInfo { Apos=26,  Astride=22,  Bytes=1156, Pattern=0x15683, Levels=L(8,28,  17,26, 23,28, 25,30) },// 21
            new VersionInfo { Apos=24,  Astride=24,  Bytes=1258, Pattern=0x168c9, Levels=L(9,28,  17,28, 23,30, 34,24) },// 22
            new VersionInfo { Apos=28,  Astride=24,  Bytes=1364, Pattern=0x177ec, Levels=L(9,30,  18,28, 25,30, 30,30) },// 23
            new VersionInfo { Apos=26,  Astride=26,  Bytes=1474, Pattern=0x18ec4, Levels=L(10,30, 20,28, 27,30, 32,30) },// 24
            new VersionInfo { Apos=30,  Astride=26,  Bytes=1588, Pattern=0x191e1, Levels=L(12,26, 21,28, 29,30, 35,30) },// 25
            new VersionInfo { Apos=28,  Astride=28,  Bytes=1706, Pattern=0x1afab, Levels=L(12,28, 23,28, 34,28, 37,30) },// 26
            new VersionInfo { Apos=32,  Astride=28,  Bytes=1828, Pattern=0x1b08e, Levels=L(12,30, 25,28, 34,30, 40,30) },// 27
            new VersionInfo { Apos=24,  Astride=24,  Bytes=1921, Pattern=0x1cc1a, Levels=L(13,30, 26,28, 35,30, 42,30) },// 28
            new VersionInfo { Apos=28,  Astride=24,  Bytes=2051, Pattern=0x1d33f, Levels=L(14,30, 28,28, 38,30, 45,30) },// 29
            new VersionInfo { Apos=24,  Astride=26,  Bytes=2185, Pattern=0x1ed75, Levels=L(15,30, 29,28, 40,30, 48,30) },// 30
            new VersionInfo { Apos=28,  Astride=26,  Bytes=2323, Pattern=0x1f250, Levels=L(16,30, 31,28, 43,30, 51,30) },// 31
            new VersionInfo { Apos=32,  Astride=26,  Bytes=2465, Pattern=0x209d5, Levels=L(17,30, 33,28, 45,30, 54,30) },// 32
            new VersionInfo { Apos=28,  Astride=28,  Bytes=2611, Pattern=0x216f0, Levels=L(18,30, 35,28, 48,30, 57,30) },// 33
            new VersionInfo { Apos=32,  Astride=28,  Bytes=2761, Pattern=0x228ba, Levels=L(19,30, 37,28, 51,30, 60,30) },// 34
            new VersionInfo { Apos=28,  Astride=24,  Bytes=2876, Pattern=0x2379f, Levels=L(19,30, 38,28, 53,30, 63,30) },// 35
            new VersionInfo { Apos=22,  Astride=26,  Bytes=3034, Pattern=0x24b0b, Levels=L(20,30, 40,28, 56,30, 66,30) },// 36
            new VersionInfo { Apos=26,  Astride=26,  Bytes=3196, Pattern=0x2542e, Levels=L(21,30, 43,28, 59,30, 70,30) },// 37
            new VersionInfo { Apos=30,  Astride=26,  Bytes=3362, Pattern=0x26a64, Levels=L(22,30, 45,28, 62,30, 74,30) },// 38
            new VersionInfo { Apos=24,  Astride=28,  Bytes=3532, Pattern=0x27541, Levels=L(24,30, 47,28, 65,30, 77,30) },// 39
            new VersionInfo { Apos=28,  Astride=28,  Bytes=3706, Pattern=0x28c69, Levels=L(25,30, 49,28, 68,30, 81,30) },// 40
        };
    }

    private static LevelInfo[] L(int nb0,int c0, int nb1,int c1, int nb2,int c2, int nb3,int c3)
        => new[] {
            new LevelInfo{NBlock=nb0,Check=c0},
            new LevelInfo{NBlock=nb1,Check=c1},
            new LevelInfo{NBlock=nb2,Check=c2},
            new LevelInfo{NBlock=nb3,Check=c3},
        };

    public static int DataBytes(int version, QrLevel level)
    {
        var vt = Vtab[version];
        var lev = vt.Levels[(int)level];
        return vt.Bytes - lev.NBlock * lev.Check;
    }
}

// ---- QR Coding (Plan) -----------------------------------------------------

internal static class QrCoding
{
    public const int MinVersion = 1;
    public const int MaxVersion = 40;

    // The GF(256) field for QR error correction: poly=0x11d, alpha=2
    public static readonly Gf256Field Field = new Gf256Field(0x11d, 2);

    // Mask functions — exactly as in Go (i=row/y, j=col/x)
    private static readonly Func<int,int,bool>[] MaskFuncs = new Func<int,int,bool>[]
    {
        (i,j) => (i+j)%2==0,
        (i,j) => i%2==0,
        (i,j) => j%3==0,
        (i,j) => (i+j)%3==0,
        (i,j) => (i/2+j/3)%2==0,
        (i,j) => i*j%2+i*j%3==0,
        (i,j) => (i*j%2+i*j%3)%2==0,
        (i,j) => (i*j%3+(i+j)%2)%2==0,
    };

    public static bool MaskInvert(int m, int y, int x)
    {
        if (m < 0) return false;
        return MaskFuncs[m](y, x);
    }

    // NewPlan builds and returns a Plan for given version, level, mask
    public static QrPlan NewPlan(int version, QrLevel level, int mask)
    {
        var p = VPlan(version);
        FPlan(level, mask, p);
        LPlan(version, level, p);
        MPlan(mask, p);
        return p;
    }

    // vplan creates a version-only Plan
    private static QrPlan VPlan(int v)
    {
        var p = new QrPlan { Version = v };
        int siz = 17 + v * 4;
        p.Pixel = Grid(siz);

        // Timing markers
        const int ti = 6;
        for (int i = 0; i < siz; i++)
        {
            var px = Pixel.ForRole(PixelRole.Timing);
            if ((i & 1) == 0) px = px.WithBlack();
            p.Pixel[i][ti] = px;
            p.Pixel[ti][i] = px;
        }

        // Position boxes
        PosBox(p.Pixel, 0, 0);
        PosBox(p.Pixel, siz - 7, 0);
        PosBox(p.Pixel, 0, siz - 7);

        // Alignment boxes
        var info = VersionTable.Vtab[v];
        for (int x = 4; x + 5 < siz;)
        {
            for (int y = 4; y + 5 < siz;)
            {
                if (!((x < 7 && y < 7) || (x < 7 && y + 5 >= siz - 7) || (x + 5 >= siz - 7 && y < 7)))
                    AlignBox(p.Pixel, x, y);
                if (y == 4) y = info.Apos;
                else y += info.Astride;
            }
            if (x == 4) x = info.Apos;
            else x += info.Astride;
        }

        // Version pattern
        int pat = VersionTable.Vtab[v].Pattern;
        if (pat != 0)
        {
            int vv = pat;
            for (int x = 0; x < 6; x++)
            {
                for (int y = 0; y < 3; y++)
                {
                    var px = Pixel.ForRole(PixelRole.PVersion);
                    if ((vv & 1) != 0) px = px.WithBlack();
                    p.Pixel[siz - 11 + y][x] = px;
                    p.Pixel[x][siz - 11 + y] = px;
                    vv >>= 1;
                }
            }
        }

        // Lonely black pixel
        p.Pixel[siz - 8][8] = Pixel.ForRole(PixelRole.Unused).Or(Pixel.ForRole(PixelRole.None).WithBlack());
        // Equivalent to Unused.Pixel() | Black in Go
        p.Pixel[siz - 8][8] = new Pixel(((uint)PixelRole.Unused << 2) | 1u); // Black=1

        return p;
    }

    // fplan adds format pixels
    private static void FPlan(QrLevel l, int m, QrPlan p)
    {
        uint fb = (uint)((int)l ^ 1) << 13; // L=01,M=00,Q=11,H=10
        fb |= (uint)m << 10;
        const uint formatPoly = 0x537;
        uint rem = fb;
        for (int i = 14; i >= 10; i--)
        {
            if ((rem & (1u << i)) != 0)
                rem ^= formatPoly << (i - 10);
        }
        fb |= rem;
        uint invert = 0x5412;
        int siz = p.Pixel.Length;
        for (uint i = 0; i < 15; i++)
        {
            var pix = Pixel.ForRole(PixelRole.Format).Or(Pixel.OffsetPixel(i));
            if (((fb >> (int)i) & 1) == 1) pix = pix.WithBlack();
            if (((invert >> (int)i) & 1) == 1) pix = pix.XorBlackInvert();
            // top left
            if (i < 6)
                p.Pixel[(int)i][8] = pix;
            else if (i < 8)
                p.Pixel[(int)i + 1][8] = pix;
            else if (i < 9)
                p.Pixel[8][7] = pix;
            else
                p.Pixel[8][14 - (int)i] = pix;
            // bottom right
            if (i < 8)
                p.Pixel[8][siz - 1 - (int)i] = pix;
            else
                p.Pixel[siz - 1 - (14 - (int)i)][8] = pix;
        }
    }

    // lplan fills data/check pixel positions
    private static void LPlan(int v, QrLevel l, QrPlan p)
    {
        p.Level = l;
        var vt = VersionTable.Vtab[v];
        var lev = vt.Levels[(int)l];
        int nblock = lev.NBlock;
        int ne = lev.Check;
        int nd = vt.Bytes - ne * nblock;
        int nde = nd / nblock;
        int extra = nd % nblock;
        int dataBits = (nde * nblock + extra) * 8;
        int checkBits = ne * nblock * 8;

        p.DataBytes = nd;
        p.CheckBytes = ne * nblock;
        p.Blocks = nblock;

        // Make data + checksum pixel arrays
        var data = new Pixel[dataBits];
        for (int i = 0; i < dataBits; i++)
            data[i] = Pixel.ForRole(PixelRole.Data).Or(Pixel.OffsetPixel((uint)i));
        var check = new Pixel[checkBits];
        for (int i = 0; i < checkBits; i++)
            check[i] = Pixel.ForRole(PixelRole.Check).Or(Pixel.OffsetPixel((uint)(i + dataBits)));

        // Split into blocks
        var dataList = new Pixel[nblock][];
        var checkList = new Pixel[nblock][];
        int di = 0, ci = 0;
        for (int i = 0; i < nblock; i++)
        {
            int thisNd = nde;
            if (i >= nblock - extra) thisNd++;
            dataList[i] = data[di..(di + thisNd * 8)]; di += thisNd * 8;
            checkList[i] = check[ci..(ci + ne * 8)];   ci += ne * 8;
        }

        // Interleave bits
        var bits = new Pixel[dataBits + checkBits];
        int dst = 0;
        for (int i = 0; i <= nde; i++)
        {
            foreach (var b in dataList)
            {
                if (i * 8 < b.Length)
                {
                    Array.Copy(b, i * 8, bits, dst, 8);
                    dst += 8;
                }
            }
        }
        for (int i = 0; i < ne; i++)
        {
            foreach (var b in checkList)
            {
                if (i * 8 < b.Length)
                {
                    Array.Copy(b, i * 8, bits, dst, 8);
                    dst += 8;
                }
            }
        }

        // 7 remainder bits (Extra role)
        var rem = new Pixel[7];
        for (int i = 0; i < 7; i++) rem[i] = Pixel.ForRole(PixelRole.Extra);
        var src = new Pixel[bits.Length + 7];
        Array.Copy(bits, src, bits.Length);
        Array.Copy(rem, 0, src, bits.Length, 7);
        int srcIdx = 0;

        int siz = p.Pixel.Length;
        for (int x = siz; x > 0;)
        {
            for (int y = siz - 1; y >= 0; y--)
            {
                if (p.Pixel[y][x - 1].Role() == PixelRole.None)
                    p.Pixel[y][x - 1] = src[srcIdx++];
                if (p.Pixel[y][x - 2].Role() == PixelRole.None)
                    p.Pixel[y][x - 2] = src[srcIdx++];
            }
            x -= 2;
            if (x == 7) x--; // vertical timing strip
            for (int y = 0; y < siz; y++)
            {
                if (p.Pixel[y][x - 1].Role() == PixelRole.None)
                    p.Pixel[y][x - 1] = src[srcIdx++];
                if (p.Pixel[y][x - 2].Role() == PixelRole.None)
                    p.Pixel[y][x - 2] = src[srcIdx++];
            }
            x -= 2;
        }
    }

    // mplan applies mask to data/check/extra pixels
    private static void MPlan(int m, QrPlan p)
    {
        p.Mask = m;
        for (int y = 0; y < p.Pixel.Length; y++)
        {
            var row = p.Pixel[y];
            for (int x = 0; x < row.Length; x++)
            {
                var pix = row[x];
                var r = pix.Role();
                if ((r == PixelRole.Data || r == PixelRole.Check || r == PixelRole.Extra)
                    && MaskInvert(m, y, x))
                {
                    row[x] = pix.XorBlackInvert();
                }
            }
        }
    }

    private static Pixel[][] Grid(int siz)
    {
        var m = new Pixel[siz][];
        for (int i = 0; i < siz; i++) m[i] = new Pixel[siz];
        return m;
    }

    private static void PosBox(Pixel[][] m, int x, int y)
    {
        var pos = Pixel.ForRole(PixelRole.Position);
        for (int dy = 0; dy < 7; dy++)
        {
            for (int dx = 0; dx < 7; dx++)
            {
                var px = pos;
                if (dx == 0 || dx == 6 || dy == 0 || dy == 6 || (2 <= dx && dx <= 4 && 2 <= dy && dy <= 4))
                    px = px.WithBlack();
                m[y + dy][x + dx] = px;
            }
        }
        // White border
        for (int dy = -1; dy < 8; dy++)
        {
            if (0 <= y + dy && y + dy < m.Length)
            {
                if (x > 0) m[y + dy][x - 1] = pos;
                if (x + 7 < m.Length) m[y + dy][x + 7] = pos;
            }
        }
        for (int dx = -1; dx < 8; dx++)
        {
            if (0 <= x + dx && x + dx < m.Length)
            {
                if (y > 0) m[y - 1][x + dx] = pos;
                if (y + 7 < m.Length) m[y + 7][x + dx] = pos;
            }
        }
    }

    private static void AlignBox(Pixel[][] m, int x, int y)
    {
        var align = Pixel.ForRole(PixelRole.Alignment);
        for (int dy = 0; dy < 5; dy++)
        {
            for (int dx = 0; dx < 5; dx++)
            {
                var px = align;
                if (dx == 0 || dx == 4 || dy == 0 || dy == 4 || (dx == 2 && dy == 2))
                    px = px.WithBlack();
                m[y + dy][x + dx] = px;
            }
        }
    }

    // Encode data bytes into the plan's pixel grid, producing a Code
    public static QrCode EncodePlan(QrPlan p, Bits b)
    {
        b.AddCheckBytes(p.Version, p.Level);
        byte[] bytes = b.Bytes();

        var c = new QrCode
        {
            Size = p.Pixel.Length,
            Stride = (p.Pixel.Length + 7) & ~7,
        };
        c.Bitmap = new byte[c.Stride * c.Size];

        for (int y = 0; y < p.Pixel.Length; y++)
        {
            var row = p.Pixel[y];
            for (int x = 0; x < row.Length; x++)
            {
                var pix = row[x];
                var role = pix.Role();
                if (role == PixelRole.Data || role == PixelRole.Check)
                {
                    uint o = pix.Offset();
                    if ((bytes[o / 8] & (1 << (int)(7 - o % 8))) != 0)
                        pix = pix.XorBlackInvert(); // pix ^= Black (toggle black bit)
                }
                if (pix.IsBlack())
                    c.Bitmap[y * c.Stride + x / 8] |= (byte)(1 << (7 - x % 8));
            }
        }
        return c;
    }
}

// ---- Plan struct ----------------------------------------------------------

internal sealed class QrPlan
{
    public int Version;
    public QrLevel Level;
    public int Mask;
    public int DataBytes;
    public int CheckBytes;
    public int Blocks;
    public Pixel[][] Pixel = Array.Empty<Pixel[]>();
}

// ---- Code (output) --------------------------------------------------------

internal sealed class QrCode
{
    public byte[] Bitmap = Array.Empty<byte>();
    public int Size;
    public int Stride;

    public bool Black(int x, int y)
    {
        return 0 <= x && x < Size && 0 <= y && y < Size &&
               (Bitmap[y * Stride + x / 8] & (1 << (7 - x % 8))) != 0;
    }
}
