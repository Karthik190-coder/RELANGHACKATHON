// Faithful C# port of cmd/qrterminal/main.go
// CRITICAL: Console.OutputEncoding must be UTF-8 no-BOM as FIRST operation

using System.Text;
using QrTerminal;

// Must be absolute first: set UTF-8 no-BOM output before any writes
Console.OutputEncoding = new UTF8Encoding(false);

// ---- Flag parsing (manual, matching Go's flag package behavior) ----
bool verboseFlag = false;
string levelFlag = "L";
int quietZoneFlag = 2;
bool sixelDisableFlag = false;

var positionalArgs = new List<string>();
int i = 0;
string[] cliArgs = Environment.GetCommandLineArgs()[1..]; // skip program name

while (i < cliArgs.Length)
{
    string arg = cliArgs[i];
    if (arg == "-v" || arg == "--v")
    {
        verboseFlag = true;
        i++;
    }
    else if (arg == "-s" || arg == "--s")
    {
        sixelDisableFlag = true;
        i++;
    }
    else if (arg == "-l" || arg == "--l")
    {
        i++;
        if (i < cliArgs.Length) { levelFlag = cliArgs[i]; i++; }
    }
    else if (arg.StartsWith("-l="))
    {
        levelFlag = arg[3..]; i++;
    }
    else if (arg.StartsWith("--l="))
    {
        levelFlag = arg[4..]; i++;
    }
    else if (arg == "-q" || arg == "--q")
    {
        i++;
        if (i < cliArgs.Length) { int.TryParse(cliArgs[i], out quietZoneFlag); i++; }
    }
    else if (arg.StartsWith("-q="))
    {
        int.TryParse(arg[3..], out quietZoneFlag); i++;
    }
    else if (arg.StartsWith("--q="))
    {
        int.TryParse(arg[4..], out quietZoneFlag); i++;
    }
    else if (arg == "--")
    {
        i++;
        while (i < cliArgs.Length) { positionalArgs.Add(cliArgs[i]); i++; }
    }
    else if (arg.StartsWith("-") && arg.Length > 1)
    {
        // Unknown flag — skip
        i++;
    }
    else
    {
        positionalArgs.Add(arg);
        i++;
    }
}

// ---- Level parsing ----
QrLevel level = GetLevel(levelFlag);

// ---- Content ----
string content = string.Join(" ", positionalArgs);

if (content.Length < 1)
{
    // Read from stdin until EOF
    using var reader = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false));
    content = reader.ReadToEnd();
}
else if ((int)level < 0)
{
    Console.Error.WriteLine($"Invalid error correction level: {levelFlag}");
    Console.Error.WriteLine("Valid options are [L, M, H]");
    Environment.Exit(1);
}

// ---- Build config ----
var cfg = new QrTerminalConfig
{
    Level     = level,
    Writer    = Console.Out,
    QuietZone = quietZoneFlag,
    BlackChar = QrTerminalRenderer.Black,
    WhiteChar = QrTerminalRenderer.White,
};

// ---- Verbose output ----
if (verboseFlag)
{
    Console.Write($"Level: {levelFlag} \n");
    Console.Write($"Quietzone Border Size: {quietZoneFlag} \n");
    Console.Write($"Encoded data: {string.Join("\n", positionalArgs)} \n");
    Console.Write("\n");
}

// ---- Leading newline (exactly as Go: fmt.Fprint(os.Stdout, "\n")) ----
Console.Write("\n");

// ---- Generate QR ----
QrTerminalRenderer.GenerateWithConfig(content, cfg);

// ---- Helper ----
static QrLevel GetLevel(string s)
{
    return s.ToLower() switch
    {
        "l" => QrLevel.L,
        "m" => QrLevel.M,
        "h" => QrLevel.H,
        _   => (QrLevel)(-1),
    };
}
