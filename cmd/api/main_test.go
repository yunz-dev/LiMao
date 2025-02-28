package main

import (
    "net/http"
    "net/http/httptest"
    "testing"
)

func TestHeartHandler(t *testing.T) {
    // Create a request to the /heart endpoint
    req, err := http.NewRequest("GET", "/heart", nil)
    if err != nil {
        t.Fatalf("Could not create request: %v", err)
    }

    // Create a ResponseRecorder to record the response
    rr := httptest.NewRecorder()

    // Create a handler and serve the request
    handler := http.HandlerFunc(HeartHandler)
    handler.ServeHTTP(rr, req)

    // Check the status code of the response
    if status := rr.Code; status != http.StatusOK {
        t.Errorf("Expected status 200 OK, got %v", status)
    }

    // Check the response body
    expected := "Server is up and running!"
    if rr.Body.String() != expected {
        t.Errorf("Expected response body %v, got %v", expected, rr.Body.String())
    }
}
