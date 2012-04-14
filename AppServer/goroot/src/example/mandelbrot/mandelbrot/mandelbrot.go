// Copyright 2011 Google Inc. All rights reserved.
// Use of this source code is governed by the Apache 2.0
// license that can be found in the LICENSE file.

package mandelbrot

import (
	"bytes"
	"fmt"
	"http"
	"image"
	"image/png"
	"strconv"
	"template"

	"appengine"
	"appengine/memcache"
)

func init() {
	http.HandleFunc("/", frontPageHandler)
	http.HandleFunc("/tiles", tileHandler)

	for i := range color {
		// Use a broader range of color for low intensities.
		if i < 255/10 {
			color[i] = image.RGBAColor{uint8(i * 10), 0, 0, 0xFF}
		} else {
			color[i] = image.RGBAColor{0xFF, 0, uint8(i - 255/10), 0xFF}
		}
	}

	tmpl := template.New(nil)
	tmpl.SetDelims("{{", "}}")
	if err := tmpl.ParseFile("map.html"); err != nil {
		frontPage = []byte("tmpl.ParseFile failed: " + err.String())
		return
	}
	b := new(bytes.Buffer)
	data := map[string]interface{}{
		"InProd": !appengine.IsDevAppServer(),
	}
	if err := tmpl.Execute(b, data); err != nil {
		frontPage = []byte("tmpl.Execute failed: " + err.String())
		return
	}
	frontPage = b.Bytes()
}

var (
	// color is the mapping of intensity to color.
	color [256]image.Color

	frontPage []byte
)

const (
	// The number of iterations of the Mandelbrot calculation.
	// More iterations mean higher quality at the cost of more CPU time.
	iterations = 400
	// Each tile is 256 pixels wide and 256 pixels high.
	tileSize = 256
	// The maximum zoom level at which to use memcache.
	maxMemcacheLevel = 6
)

func frontPageHandler(w http.ResponseWriter, r *http.Request) {
	w.Write(frontPage)
}

// tileHandler implements a tile renderer for use with the Google Maps JavaScript API.
// See http://code.google.com/apis/maps/documentation/javascript/maptypes.html#ImageMapTypes
func tileHandler(w http.ResponseWriter, r *http.Request) {
	c := appengine.NewContext(r)

	x, _ := strconv.Atoi(r.FormValue("x"))
	y, _ := strconv.Atoi(r.FormValue("y"))
	z, _ := strconv.Atoi(r.FormValue("z"))

	w.Header().Set("Content-Type", "image/png")

	// Try memcache first.
	key := fmt.Sprintf("mandelbrot:%d/%d/%d", x, y, z)
	if z < maxMemcacheLevel {
		if item, err := memcache.Get(c, key); err == nil {
			w.Write(item.Value)
			return
		}
	}

	b := render(x, y, z)
	if z < maxMemcacheLevel {
		memcache.Set(c, &memcache.Item{
			Key:        key,
			Value:      b,
			Expiration: 3600, // TTL = 1 hour
		})
	}
	w.Write(b)
}

func render(x, y, z int) []byte {
	// tileX and tileY is the absolute position of this tile at the current zoom level.
	tileX, tileY := x*tileSize, y*tileSize
	scale := 1 / float64(int(1<<uint(z))*tileSize)

	img := image.NewPaletted(tileSize, tileSize, image.PalettedColorModel(color[:]))
	for i := 0; i < tileSize; i++ {
		for j := 0; j < tileSize; j++ {
			c := complex(float64(tileX+i)*scale, float64(tileY+j)*scale)
			img.SetColorIndex(i, j, mandelbrotValue(c))
		}
	}

	buf := new(bytes.Buffer)
	png.Encode(buf, img)
	return buf.Bytes()
}

// mandelbrotValue computes a Mandelbrot value.
// An intensity value in the range [0, 255] is returned.
func mandelbrotValue(c complex128) uint8 {
	// Scale so we can fit the entire set in one tile when zoomed out.
	c = c*3.5 - complex(2.5, 1.75)

	z := complex(0, 0)
	for iter := 0; iter < iterations; iter++ {
		z = z*z + c
		if r, i := real(z), imag(z); r*r+i*i > 4 {
			return uint8((255*iter + (iterations / 2)) / iterations)
		}
	}
	return 0
}
