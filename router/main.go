package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"math"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

// Config is the on-disk router configuration.
//
// The first implementation deliberately uses JSON instead of YAML so the router
// can be built with the Go standard library only. This keeps RPM packaging simple.
type Config struct {
	Listen                     string          `json:"listen"`
	HealthCheckIntervalSeconds int             `json:"health_check_interval_seconds"`
	Backends                   []BackendConfig `json:"backends"`
}

// BackendConfig declares one Ollama backend/node known by the router.
type BackendConfig struct {
	Name    string `json:"name"`
	URL     string `json:"url"`
	Weight  int    `json:"weight"`
	Enabled bool   `json:"enabled"`
}

// Backend is the runtime state for one configured backend.
type Backend struct {
	Name    string
	URL     *url.URL
	Weight  int
	Enabled bool
	Proxy   *httputil.ReverseProxy

	Healthy atomic.Bool
	Active  atomic.Int64
	Latency atomic.Int64 // last healthcheck latency in milliseconds

	mu       sync.RWMutex
	LastErr  string
	LastSeen time.Time
}

// Router owns the backend registry and volatile session affinity map.
type Router struct {
	backends []*Backend
	sessions map[string]string // session_id -> backend name
	mu       sync.RWMutex
}

func main() {
	configPath := flag.String("config", "router/config.example.json", "path to router JSON config")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	router, err := newRouter(cfg)
	if err != nil {
		log.Fatalf("init router: %v", err)
	}

	interval := time.Duration(cfg.HealthCheckIntervalSeconds) * time.Second
	if interval <= 0 {
		interval = 10 * time.Second
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Run one immediate healthcheck before accepting traffic, then continue in
	// the background. A backend starts unhealthy until it answers /api/version.
	router.checkAll(ctx)
	go router.healthLoop(ctx, interval)

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", router.handleHealthz)
	mux.HandleFunc("/routes", router.handleRoutes)
	mux.HandleFunc("/", router.handleProxy)

	listen := cfg.Listen
	if listen == "" {
		listen = "127.0.0.1:8090"
	}

	log.Printf("ollama-grid-router listening on %s", listen)
	if err := http.ListenAndServe(listen, mux); err != nil {
		log.Fatal(err)
	}
}

func loadConfig(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}

	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return Config{}, err
	}

	if len(cfg.Backends) == 0 {
		return Config{}, errors.New("config must declare at least one backend")
	}

	return cfg, nil
}

func newRouter(cfg Config) (*Router, error) {
	r := &Router{
		backends: make([]*Backend, 0, len(cfg.Backends)),
		sessions: make(map[string]string),
	}

	seen := make(map[string]bool)
	for _, bcfg := range cfg.Backends {
		if bcfg.Name == "" {
			return nil, errors.New("backend name cannot be empty")
		}
		if seen[bcfg.Name] {
			return nil, fmt.Errorf("duplicated backend name %q", bcfg.Name)
		}
		seen[bcfg.Name] = true

		parsed, err := url.Parse(bcfg.URL)
		if err != nil {
			return nil, fmt.Errorf("backend %s url: %w", bcfg.Name, err)
		}
		if parsed.Scheme == "" || parsed.Host == "" {
			return nil, fmt.Errorf("backend %s url must include scheme and host", bcfg.Name)
		}

		weight := bcfg.Weight
		if weight <= 0 {
			weight = 1
		}

		backend := &Backend{
			Name:    bcfg.Name,
			URL:     parsed,
			Weight:  weight,
			Enabled: bcfg.Enabled,
		}
		backend.Proxy = newBackendProxy(backend)
		r.backends = append(r.backends, backend)
	}

	return r, nil
}

func newBackendProxy(backend *Backend) *httputil.ReverseProxy {
	proxy := httputil.NewSingleHostReverseProxy(backend.URL)
	originalDirector := proxy.Director

	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.Host = backend.URL.Host
		req.Header.Set("X-Ollama-Grid-Backend", backend.Name)
	}

	proxy.ErrorHandler = func(w http.ResponseWriter, req *http.Request, err error) {
		backend.setError(err.Error())
		http.Error(w, "ollama-grid-router: backend proxy error", http.StatusBadGateway)
	}

	return proxy
}

func (r *Router) healthLoop(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			r.checkAll(ctx)
		}
	}
}

func (r *Router) checkAll(ctx context.Context) {
	var wg sync.WaitGroup
	for _, backend := range r.backends {
		wg.Add(1)
		go func(b *Backend) {
			defer wg.Done()
			b.check(ctx)
		}(backend)
	}
	wg.Wait()
}

func (b *Backend) check(ctx context.Context) {
	if !b.Enabled {
		b.Healthy.Store(false)
		b.setError("disabled")
		return
	}

	checkCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	checkURL := b.URL.ResolveReference(&url.URL{Path: "/api/version"})
	req, err := http.NewRequestWithContext(checkCtx, http.MethodGet, checkURL.String(), nil)
	if err != nil {
		b.Healthy.Store(false)
		b.setError(err.Error())
		return
	}

	start := time.Now()
	resp, err := http.DefaultClient.Do(req)
	latency := time.Since(start).Milliseconds()
	b.Latency.Store(latency)

	if err != nil {
		b.Healthy.Store(false)
		b.setError(err.Error())
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		b.Healthy.Store(false)
		b.setError(fmt.Sprintf("healthcheck status %d", resp.StatusCode))
		return
	}

	b.Healthy.Store(true)
	b.setError("")
}

func (b *Backend) setError(message string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.LastErr = message
	b.LastSeen = time.Now()
}

func (r *Router) handleHealthz(w http.ResponseWriter, req *http.Request) {
	healthy := 0
	for _, b := range r.backends {
		if b.Enabled && b.Healthy.Load() {
			healthy++
		}
	}

	status := http.StatusOK
	if healthy == 0 {
		status = http.StatusServiceUnavailable
	}

	writeJSON(w, status, map[string]any{
		"ok":               healthy > 0,
		"healthy_backends": healthy,
		"total_backends":   len(r.backends),
	})
}

func (r *Router) handleRoutes(w http.ResponseWriter, req *http.Request) {
	type backendStatus struct {
		Name     string `json:"name"`
		URL      string `json:"url"`
		Enabled  bool   `json:"enabled"`
		Healthy  bool   `json:"healthy"`
		Weight   int    `json:"weight"`
		Active   int64  `json:"active_requests"`
		Latency  int64  `json:"latency_ms"`
		LastErr  string `json:"last_error,omitempty"`
		LastSeen string `json:"last_seen,omitempty"`
	}

	items := make([]backendStatus, 0, len(r.backends))
	for _, b := range r.backends {
		b.mu.RLock()
		lastErr := b.LastErr
		lastSeen := ""
		if !b.LastSeen.IsZero() {
			lastSeen = b.LastSeen.Format(time.RFC3339)
		}
		b.mu.RUnlock()

		items = append(items, backendStatus{
			Name:    b.Name,
			URL:     b.URL.String(),
			Enabled: b.Enabled,
			Healthy: b.Healthy.Load(),
			Weight:  b.Weight,
			Active:  b.Active.Load(),
			Latency: b.Latency.Load(),
			LastErr: lastErr,
			LastSeen: lastSeen,
		})
	}

	writeJSON(w, http.StatusOK, map[string]any{"backends": items})
}

func (r *Router) handleProxy(w http.ResponseWriter, req *http.Request) {
	backend := r.pickBackend(req)
	if backend == nil {
		http.Error(w, "ollama-grid-router: no healthy backend available", http.StatusServiceUnavailable)
		return
	}

	backend.Active.Add(1)
	defer backend.Active.Add(-1)

	w.Header().Set("X-Ollama-Grid-Backend", backend.Name)
	backend.Proxy.ServeHTTP(w, req)
}

func (r *Router) pickBackend(req *http.Request) *Backend {
	sessionID := req.Header.Get("X-Ollama-Grid-Session")
	if sessionID != "" {
		if backend := r.backendForSession(sessionID); backend != nil && backend.Healthy.Load() && backend.Enabled {
			return backend
		}
	}

	var best *Backend
	bestScore := math.Inf(1)

	for _, backend := range r.backends {
		if !backend.Enabled || !backend.Healthy.Load() {
			continue
		}

		score := backendScore(backend)
		if score < bestScore {
			best = backend
			bestScore = score
		}
	}

	if best != nil && sessionID != "" {
		r.setSessionBackend(sessionID, best.Name)
	}

	return best
}

func backendScore(b *Backend) float64 {
	active := float64(b.Active.Load())
	latency := float64(b.Latency.Load())
	if latency <= 0 {
		latency = 1
	}

	// Lower score wins.
	// Weight represents relative backend capacity. CUDA may have weight 10,
	// CPU weight 1, etc. Active requests are divided by weight so stronger
	// backends naturally receive more traffic.
	activePressure := active / float64(b.Weight)
	latencyPressure := latency / 1000.0
	return activePressure + latencyPressure
}

func (r *Router) backendForSession(sessionID string) *Backend {
	r.mu.RLock()
	name := r.sessions[sessionID]
	r.mu.RUnlock()
	if name == "" {
		return nil
	}

	for _, backend := range r.backends {
		if backend.Name == name {
			return backend
		}
	}
	return nil
}

func (r *Router) setSessionBackend(sessionID, backendName string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.sessions[sessionID] = backendName
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		log.Printf("write json: %v", err)
	}
}
