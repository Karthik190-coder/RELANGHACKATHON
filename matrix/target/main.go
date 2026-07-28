package main

import (
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"strings"
	"time"
)

var matrixChars = []string{
	"- ", "* ", "% ", "& ", "# ", "@ ", "1 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 ", "8 ", "9 ", "0 ",
	"ア", "ィ", "イ", "ゥ", "ウ", "ェ", "エ", "ォ", "オ", "カ", "ガ", "キ", "ギ", "ク", "グ", "ケ", "ゲ", "コ",
	"ゴ", "サ", "ザ", "シ", "ジ", "ス", "ズ", "セ", "ゼ", "ソ", "ゾ", "タ", "ダ", "チ", "ヂ", "ッ", "ツ", "ヅ", "テ",
}

var terminalColors = [2]string{"22", "28"}

const (
	resetColor      = "\033[0m"
	textWhite       = "\033[38;5;15m"
	hideCursor      = "\033[?25l"
	showCursor      = "\033[?25h"
)

func textRandomColor(rng *rand.Rand) string {
	return "\033[38;5;" + terminalColors[rng.Intn(2)] + "m"
}

func getCharacter(rng *rand.Rand) string {
	return matrixChars[rng.Intn(len(matrixChars))]
}

func main() {
	screenWidth := 150
	lineCount := 750
	lineSpeed := 0.1

	rng := rand.New(rand.NewSource(time.Now().UnixNano()))

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt)
	go func() {
		<-sigChan
		fmt.Print(showCursor)
		fmt.Print(resetColor)
		os.Exit(0)
	}()

	fmt.Print(hideCursor)
	defer fmt.Print(showCursor)

	lineArray := make([]int, screenWidth)
	for i := 0; i < screenWidth; i++ {
		lineArray[i] = 1
	}

	for l := 0; l < lineCount; l++ {
		var sb strings.Builder

		for m := 0; m < screenWidth; m++ {
			n := lineArray[m]
			if n == 1 || n == 2 {
				if n == 2 {
					sb.WriteString(textWhite)
					sb.WriteString(getCharacter(rng))
					lineArray[m] = 1
				} else {
					sb.WriteString(textRandomColor(rng))
					sb.WriteString(getCharacter(rng))
				}
				if rng.Intn(30) == 0 {
					lineArray[m] = 0
				}
			} else {
				sb.WriteString(textRandomColor(rng))
				sb.WriteString(" ")
				if rng.Intn(60) == 0 {
					lineArray[m] = 2
				}
			}
		}

		fmt.Println(sb.String())
		time.Sleep(time.Duration(float64(time.Second) * lineSpeed))
	}

	fmt.Print(resetColor)
}
