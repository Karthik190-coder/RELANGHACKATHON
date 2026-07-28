package main

import (
	"bufio"
	"fmt"
	"math"
	"os"
)

const (
	width   = 80
	height  = 22
	buflen  = width * height
	luma    = ".,-~:;=!*#$@"
	lumaLen = 12
)

func main() {
	angle1 := 0.0
	angle2 := 0.0

	w := bufio.NewWriterSize(os.Stdout, 1760*4)
	fmt.Fprint(w, "\033[2J")
	w.Flush()

	for {
		pixels := make([]byte, buflen)
		for k := range pixels {
			pixels[k] = ' '
		}
		zBuffer := make([]float64, buflen)

		sinA1 := math.Sin(angle1)
		cosA1 := math.Cos(angle1)
		sinA2 := math.Sin(angle2)
		cosA2 := math.Cos(angle2)

		for j := 0; j < 628; j += 7 {
			jj := float64(j) / 100.0
			sinJ := math.Sin(jj)
			cosJ := math.Cos(jj)
			h := cosJ + 2.0

			for i := 0; i < 628; i += 2 {
				ii := float64(i) / 100.0
				sinI := math.Sin(ii)
				cosI := math.Cos(ii)

				distance := 1.0 / (sinI*h*sinA1 + sinJ*cosA1 + 5.0)
				sinH := sinI*h*cosA1 - sinJ*sinA1

				x := int(40.0 + 30.0*distance*(cosI*h*cosA2-sinH*sinA2))
				y := int(12.0 + 15.0*distance*(cosI*h*sinA2+sinH*cosA2))

				index := x + width*y

				brightness := int(8.0 * ((sinJ*sinA1-sinI*cosJ*cosA1)*cosA2 -
					sinI*cosJ*sinA1 - sinJ*cosA1 - cosI*cosJ*sinA2))

				if y >= 0 && y < height && x >= 0 && x < width && distance > zBuffer[index] {
					zBuffer[index] = distance
					idx := brightness
					if idx <= 0 {
						idx = 0
					}
					if idx >= lumaLen {
						idx = lumaLen - 1
					}
					pixels[index] = luma[idx]
				}
			}
		}

		fmt.Fprintf(w, "\033[H%s", string(pixels))
		w.Flush()

		angle1 += 0.30
		angle2 += 0.15
	}
}
