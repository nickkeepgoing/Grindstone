package main

import (
	"context"
	"errors"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"grindstone/internal/datasets"
	"grindstone/internal/handler"
)

func main() {
	addr := flag.String("addr", ":8080", "HTTP listen address")
	dataDir := flag.String("data", "./data", "root directory containing dataset folders")
	flag.Parse()

	store := datasets.NewStore(*dataDir)
	if err := store.LoadAll(); err != nil {
		log.Fatalf("failed to load datasets: %v", err)
	}

	srv := handler.New(store)
	mux := http.NewServeMux()
	srv.Routes(mux)

	httpServer := &http.Server{
		Addr:         *addr,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
	}

	// graceful shutdown
	go func() {
		log.Printf("[grindstone] listening on %s", *addr)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("server error: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	log.Println("[grindstone] shutting down...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = httpServer.Shutdown(ctx)
}
