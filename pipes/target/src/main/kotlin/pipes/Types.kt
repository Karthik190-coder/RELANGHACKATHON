package pipes

enum class Direction(val value: Int) {
    UP(0),
    RIGHT(1),
    DOWN(2),
    LEFT(3);

    companion object {
        fun fromInt(value: Int) = values().first { it.value == value }
    }
}

enum class PipeStyle(val value: Int) {
    HEAVY(0),
    CURVED(1),
    LIGHT(2),
    DOUBLE(3),
    KNOBBY(4),
    ANGLES(5),
    DOTS(6),
    DOTS_O(7),
    SLASHES(8),
    MIXED(9);

    companion object {
        fun fromInt(value: Int) = values().first { it.value == value }
    }
}

data class PipeConfig(
    var pipes: Int = 1,
    var fps: Int = 75,
    var steady: Int = 13,
    var limit: Int = 2000,
    var randomStart: Boolean = false,
    var bold: Boolean = true,
    var color: Boolean = true,
    var keepStyle: Boolean = false,
    var colors: List<Int> = listOf(1, 2, 3, 4, 5, 6, 7, 0),
    var pipeTypes: List<Int> = listOf(0)
)

data class Pipe(
    var x: Int,
    var y: Int,
    var direction: Direction,
    var pipeType: Int,
    var color: Int,
    var attr: String
)
