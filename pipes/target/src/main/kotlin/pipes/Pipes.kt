package pipes

import org.jline.terminal.Terminal
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.random.Random

class PipesScreen(private val terminal: Terminal, val config: PipeConfig) {
    val renderer = Renderer(terminal, config)
    private val pipes = mutableListOf<Pipe>()
    private var height = if (terminal.height > 0) terminal.height else 24
    private var width = if (terminal.width > 0) terminal.width else 80
    private var count = 0
    var delay = 1000L / config.fps
    private val keyQueue = ConcurrentLinkedQueue<Int>()

    init {
        initPipes()
        startKeyReaderThread()
    }

    private fun startKeyReaderThread() {
        Thread {
            try {
                val r = terminal.reader()
                while (true) {
                    val key = r.read()
                    if (key == -1) break
                    keyQueue.add(key)
                }
            } catch (e: Exception) {
                // Silent exit
            }
        }.apply {
            isDaemon = true
            start()
        }
    }

    private fun initPipes() {
        for (i in 0 until config.pipes) {
            val direction = if (config.randomStart) {
                Direction.fromInt(Random.nextInt(4))
            } else {
                Direction.UP
            }
            val x = if (config.randomStart) Random.nextInt(width) else width / 2
            val y = if (config.randomStart) Random.nextInt(height) else height / 2

            val pipeType = config.pipeTypes.random()
            val color = config.colors.random()

            pipes.add(
                Pipe(
                    x = x,
                    y = y,
                    direction = direction,
                    pipeType = pipeType,
                    color = color,
                    attr = renderer.getColorAttr(color)
                )
            )
        }
    }

    fun update(): Boolean {
        // Read all keys accumulated in the queue
        while (!keyQueue.isEmpty()) {
            val key = keyQueue.poll()
            if (key != null && key != -1) {
                if (!handleKey(key)) {
                    return false
                }
            }
        }

        val newHeight = if (terminal.height > 0) terminal.height else 24
        val newWidth = if (terminal.width > 0) terminal.width else 80
        if (newHeight != height || newWidth != width) {
            height = newHeight
            width = newWidth
            renderer.clear()
        }

        updatePipes()
        renderer.refresh()

        count += pipes.size
        if (config.limit > 0 && count >= config.limit) {
            renderer.clear()
            count = 0
        }

        return true
    }

    private fun updatePipes() {
        for (pipe in pipes) {
            var x = pipe.x
            var y = pipe.y
            val oldDirection = pipe.direction

            // Update position based on direction
            if (oldDirection.value % 2 != 0) { // RIGHT or LEFT
                x += -oldDirection.value + 2
            } else { // UP or DOWN
                y += oldDirection.value - 1
            }

            // Handle wrapping
            if (x < 0 || x >= width || y < 0 || y >= height) {
                if (!config.keepStyle) {
                    pipe.pipeType = config.pipeTypes.random()
                    pipe.color = config.colors.random()
                    pipe.attr = renderer.getColorAttr(pipe.color)
                }
                x = (x % width + width) % width
                y = (y % height + height) % height
            }

            // Calculate new direction
            var newDirection = oldDirection
            if (Random.nextInt(config.steady) <= 1) {
                val turn = 2 * Random.nextInt(2) - 1 // -1 or 1
                newDirection = Direction.fromInt((oldDirection.value + turn + 4) % 4)
            }

            // Draw pipe segment
            renderer.drawPipe(pipe, oldDirection, newDirection)

            // Update pipe state
            pipe.x = x
            pipe.y = y
            pipe.direction = newDirection
        }
    }

    private fun updatePipeColors() {
        for (pipe in pipes) {
            pipe.attr = renderer.getColorAttr(pipe.color)
        }
    }

    private fun handleKey(key: Int): Boolean {
        val keyChar = if (key in 0..255) key.toChar().uppercaseChar() else ' '

        if (keyChar == 'P' && config.steady < 15) {
            config.steady += 1
        } else if (keyChar == 'O' && config.steady > 3) {
            config.steady -= 1
        } else if (keyChar == 'F' && config.fps < 100) {
            config.fps += 1
            delay = 1000L / config.fps
        } else if (keyChar == 'D' && config.fps > 20) {
            config.fps -= 1
            delay = 1000L / config.fps
        } else if (keyChar == 'B') {
            config.bold = !config.bold
            renderer.reinitColors()
            updatePipeColors()
        } else if (keyChar == 'C') {
            config.color = !config.color
            renderer.reinitColors()
            updatePipeColors()
        } else if (keyChar == 'K') {
            config.keepStyle = !config.keepStyle
        } else if (keyChar == '?' || key == 27) { // ESC or ?
            return false
        }
        return true
    }
}
