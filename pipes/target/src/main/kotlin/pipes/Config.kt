package pipes

import com.google.gson.GsonBuilder
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.File

object ConfigManager {
    private val gson = GsonBuilder().setPrettyPrinting().create()

    private fun getConfigDir(): File {
        val os = System.getProperty("os.name").lowercase()
        val home = System.getProperty("user.home")
        return if (os.contains("win")) {
            File(home, "AppData/Local/pipes-py")
        } else {
            File(home, ".config/pipes-py")
        }
    }

    private val configFile = File(getConfigDir(), "config.json")
    val defaultConfig = PipeConfig()

    fun loadConfig(): PipeConfig {
        if (!configFile.exists()) return defaultConfig.copy()
        return try {
            val jsonStr = configFile.readText()
            val json = JsonParser.parseString(jsonStr).asJsonObject
            PipeConfig(
                pipes = json.get("pipes")?.asInt ?: defaultConfig.pipes,
                fps = json.get("fps")?.asInt ?: defaultConfig.fps,
                steady = json.get("steady")?.asInt ?: defaultConfig.steady,
                limit = json.get("limit")?.asInt ?: defaultConfig.limit,
                randomStart = json.get("random_start")?.asBoolean ?: defaultConfig.randomStart,
                bold = json.get("bold")?.asBoolean ?: defaultConfig.bold,
                color = json.get("color")?.asBoolean ?: defaultConfig.color,
                keepStyle = json.get("keep_style")?.asBoolean ?: defaultConfig.keepStyle,
                colors = json.getAsJsonArray("colors")?.map { it.asInt } ?: defaultConfig.colors,
                pipeTypes = json.getAsJsonArray("pipe_types")?.map { it.asInt } ?: defaultConfig.pipeTypes
            )
        } catch (e: Exception) {
            defaultConfig.copy()
        }
    }

    fun saveConfig(config: PipeConfig) {
        try {
            configFile.parentFile.mkdirs()
            val json = JsonObject().apply {
                addProperty("pipes", config.pipes)
                addProperty("fps", config.fps)
                addProperty("steady", config.steady)
                addProperty("limit", config.limit)
                addProperty("random_start", config.randomStart)
                addProperty("bold", config.bold)
                addProperty("color", config.color)
                addProperty("keep_style", config.keepStyle)
                add("colors", gson.toJsonTree(config.colors))
                add("pipe_types", gson.toJsonTree(config.pipeTypes))
            }
            configFile.writeText(gson.toJson(json))
        } catch (e: Exception) {
            // Ignore writing error
        }
    }
}
