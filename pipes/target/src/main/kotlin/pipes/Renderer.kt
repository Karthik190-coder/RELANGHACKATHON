package pipes

import org.jline.terminal.Terminal

class Renderer(private val terminal: Terminal, private val config: PipeConfig) {
    private val PIPE_SETS = listOf(
        "┃┏ ┓┛━┓  ┗┃┛┗ ┏━",
        "│╭ ╮╯─╮  ╰│╯╰ ╭─",
        "│┌ ┐┘─┐  └│┘└ ┌─",
        "║╔ ╗╝═╗  ╚║╝╚ ╔═",
        "|+ ++-+  +|++ +-",
        "|/ \\\\ /-\\\\  \\\\|/\\\\ /",
        ".o ....  .... .o",
        ".o oo.o  o.oo o.",
        "-\\\\ /\\\\|/  /-\\\\/ \\\\|",
        "╿┍ ┑┚╼┒  ┕╽┙┖ ┎╾"
    )

    private val sets = mutableListOf<Char>()
    private val outputBuffer = StringBuilder()

    init {
        prepareSets()
        // Hide cursor: ESC [ ? 25 l
        print("\u001B[?25l")
        clear()
        refresh()
    }

    private fun prepareSets() {
        for (pipeSet in PIPE_SETS) {
            val padded = (pipeSet + " ".repeat(16)).substring(0, 16)
            for (char in padded) {
                sets.add(char)
            }
        }
    }

    fun getColorAttr(color: Int): String {
        if (!config.color) {
            return if (config.bold) "\u001B[1m" else "\u001B[0m"
        }
        val maxColors = 8
        val cursesColor = color % maxColors
        val ansiColor = 30 + cursesColor
        return if (config.bold) {
            "\u001B[1;${ansiColor}m"
        } else {
            "\u001B[0;${ansiColor}m"
        }
    }

    fun drawPipe(pipe: Pipe, oldDirection: Direction, newDirection: Direction) {
        val base = pipe.pipeType * 16
        val index = base + oldDirection.value * 4 + newDirection.value
        val char = if (index >= 0 && index < sets.size) sets[index] else '?'

        val row = pipe.y + 1
        val col = pipe.x + 1
        outputBuffer.append("\u001B[$row;${col}H${pipe.attr}$char")
    }

    fun clear() {
        outputBuffer.append("\u001B[2J\u001B[H")
    }

    fun refresh() {
        print(outputBuffer.toString())
        System.out.flush()
        outputBuffer.setLength(0)
    }

    fun reinitColors() {
        // Colors are computed dynamically, so reinit is a no-op except for refreshing active pipe attributes
    }

    fun cleanup() {
        // Show cursor: ESC [ ? 25 h, and reset styles
        print("\u001B[?25h\u001B[0m")
        System.out.flush()
    }
}
