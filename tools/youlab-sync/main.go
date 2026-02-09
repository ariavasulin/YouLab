package main

import (
	"github.com/sirupsen/logrus"
	"github.com/youlab/youlab-sync/cmd"
)

func init() {
	// Configure logrus
	logrus.SetFormatter(&logrus.TextFormatter{
		FullTimestamp:   true,
		TimestampFormat: "2006-01-02 15:04:05",
	})
}

func main() {
	cmd.Execute()
}
