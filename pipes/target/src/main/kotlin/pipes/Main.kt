package pipes

import org.jline.terminal.Terminal
import org.jline.terminal.TerminalBuilder
import kotlin.system.exitProcess

fun printHelp() {
    println("Usage: java -jar pipes.jar [options]")
    println("Options:")
    println("  -p, --pipes N         number of pipes")
    println("  -f, --fps N           frames per second (20-100)")
    println("  -s, --steady N        steadiness (5-15)")
    println("  -r, --limit N         character limit before screen reset")
    println("  -R, --random          start pipes at random positions")
    println("  -B, --no-bold         disable bold characters")
    println("  -C, --no-color        disable colors")
    println("  -P, --pipe-style N    change pipe style (0-9)")
    println("  -K, --keep-style      keep pipe style when wrapping around screen")
    println("  -S, --save-config     save current settings as default")
    println("  -v, --version         show version")
}

fun main(args: Array<String>) {
    val os = System.getProperty("os.name").lowercase()
    if (os.contains("win")) {
        try {
            ProcessBuilder("chcp", "65001").start().waitFor()
        } catch (e: Exception) {
            // Ignore if chcp is not available
        }
    }
    System.setOut(java.io.PrintStream(System.out, true, "UTF-8"))
    val config = ConfigManager.loadConfig()
    var saveRequested = false

    var idx = 0
    while (idx < args.size) {
        when (val arg = args[idx]) {
            "-p", "--pipes" -> {
                if (idx + 1 < args.size) {
                    config.pipes = maxOf(1, args[++idx].toInt())
                }
            }
            "-f", "--fps" -> {
                if (idx + 1 < args.size) {
                    config.fps = maxOf(20, minOf(100, args[++idx].toInt()))
                }
            }
            "-s", "--steady" -> {
                if (idx + 1 < args.size) {
                    config.steady = maxOf(5, minOf(15, args[++idx].toInt()))
                }
            }
            "-r", "--limit" -> {
                if (idx + 1 < args.size) {
                    config.limit = maxOf(0, args[++idx].toInt())
                }
            }
            "-R", "--random" -> {
                config.randomStart = true
            }
            "-B", "--no-bold" -> {
                config.bold = false
            }
            "-C", "--no-color" -> {
                config.color = false
            }
            "-P", "--pipe-style" -> {
                if (idx + 1 < args.size) {
                    val style = args[++idx].toInt()
                    if (style in 0..9) {
                        config.pipeTypes = listOf(style)
                    }
                }
            }
            "-K", "--keep-style" -> {
                config.keepStyle = true
            }
            "-S", "--save-config" -> {
                saveRequested = true
            }
            "-v", "--version" -> {
                println("pipes-py v2.0.0 (Kotlin Port)")
                exitProcess(0)
            }
            "-h", "--help" -> {
                printHelp()
                exitProcess(0)
            }
            else -> {
                System.err.println("Unknown option: $arg")
                printHelp()
                exitProcess(1)
            }
        }
        idx++
    }

    if (saveRequested) {
        ConfigManager.saveConfig(config)
    }

    val terminal = try {
        val t = TerminalBuilder.builder().system(true).build()
        t.enterRawMode()
        t
    } catch (e: Exception) {
        System.err.println("Error initializing terminal: ${e.message}")
        exitProcess(1)
    }

    val screen = PipesScreen(terminal, config)

    // Add a shutdown hook to clean up terminal raw mode
    Runtime.getRuntime().addShutdownHook(Thread {
        screen.renderer.cleanup()
        terminal.close()
    })

    try {
        var running = true
        while (running) {
            val startTime = System.currentTimeMillis()
            running = screen.update()
            val elapsedTime = System.currentTimeMillis() - startTime
            val sleepTime = screen.delay - elapsedTime
            if (sleepTime > 0) {
                Thread.sleep(sleepTime)
            }
        }
    } catch (e: InterruptedException) {
        // Normal exit
    } catch (e: Exception) {
        screen.renderer.cleanup()
        terminal.close()
        e.printStackTrace()
        exitProcess(1)
    }

    screen.renderer.cleanup()
    terminal.close()
}
