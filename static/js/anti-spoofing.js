/**
 * Advanced Anti-Spoofing Frontend Component
 * Provides real-time anti-spoofing analysis and user feedback
 */

class AntiSpoofingManager {
    constructor(options = {}) {
        this.options = {
            videoElement: options.videoElement || null,
            canvasElement: options.canvasElement || null,
            statusElement: options.statusElement || null,
            confidenceElement: options.confidenceElement || null,
            detailsElement: options.detailsElement || null,
            enableRealTime: options.enableRealTime || false,
            checkInterval: options.checkInterval || 2000, // 2 seconds
            confidenceThreshold: options.confidenceThreshold || 0.7,
            ...options
        };
        
        this.isAnalyzing = false;
        this.analysisHistory = [];
        this.maxHistorySize = 10;
        this.stream = null;
        this.analysisTimer = null;
        
        this.initializeElements();
    }
    
    initializeElements() {
        // Create status display if not provided
        if (!this.options.statusElement) {
            this.createStatusDisplay();
        }
        
        // Set up canvas if not provided
        if (!this.options.canvasElement && this.options.videoElement) {
            this.setupCanvas();
        }
    }
    
    createStatusDisplay() {
        const container = document.createElement('div');
        container.className = 'anti-spoofing-status bg-white p-4 rounded-lg shadow-lg border-l-4';
        container.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <h4 class="font-semibold text-gray-800">🛡️ Anti-Spoofing Status</h4>
                <div class="flex items-center">
                    <div id="spoofing-indicator" class="w-3 h-3 rounded-full bg-yellow-500 mr-2"></div>
                    <span id="spoofing-status" class="text-sm font-medium text-gray-600">Initializing...</span>
                </div>
            </div>
            <div class="mb-2">
                <div class="flex justify-between text-sm mb-1">
                    <span class="text-gray-600">Confidence</span>
                    <span id="spoofing-confidence" class="font-medium text-gray-800">--</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div id="confidence-bar" class="bg-blue-500 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
            </div>
            <div id="spoofing-details" class="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                Ready for analysis...
            </div>
            <div id="spoofing-checks" class="mt-2 text-xs">
                <div class="grid grid-cols-2 gap-1">
                    <div class="flex items-center">
                        <span id="blink-check" class="w-2 h-2 rounded-full bg-gray-300 mr-1"></span>
                        <span>Blink Detection</span>
                    </div>
                    <div class="flex items-center">
                        <span id="texture-check" class="w-2 h-2 rounded-full bg-gray-300 mr-1"></span>
                        <span>Texture Analysis</span>
                    </div>
                    <div class="flex items-center">
                        <span id="color-check" class="w-2 h-2 rounded-full bg-gray-300 mr-1"></span>
                        <span>Color Analysis</span>
                    </div>
                    <div class="flex items-center">
                        <span id="motion-check" class="w-2 h-2 rounded-full bg-gray-300 mr-1"></span>
                        <span>Motion Detection</span>
                    </div>
                </div>
            </div>
        `;
        
        // Insert after video element or at the beginning of body
        const target = this.options.videoElement?.parentElement || document.body;
        target.appendChild(container);
        
        // Update element references
        this.options.statusElement = document.getElementById('spoofing-status');
        this.options.confidenceElement = document.getElementById('spoofing-confidence');
        this.options.detailsElement = document.getElementById('spoofing-details');
    }
    
    setupCanvas() {
        const canvas = document.createElement('canvas');
        canvas.style.display = 'none';
        document.body.appendChild(canvas);
        this.options.canvasElement = canvas;
    }
    
    async startRealTimeAnalysis() {
        if (!this.options.enableRealTime || !this.options.videoElement) {
            return;
        }
        
        try {
            // Start camera
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    width: 640, 
                    height: 480,
                    facingMode: 'user'
                } 
            });
            this.options.videoElement.srcObject = this.stream;
            
            await this.options.videoElement.play();
            
            // Start periodic analysis
            this.startPeriodicAnalysis();
            
            this.updateStatus('🟢 Live', 'Ready for analysis', 'text-green-600');
            
        } catch (error) {
            console.error('Camera access failed:', error);
            this.updateStatus('🔴 Error', 'Camera access denied', 'text-red-600');
        }
    }
    
    startPeriodicAnalysis() {
        if (this.analysisTimer) {
            clearInterval(this.analysisTimer);
        }
        
        this.analysisTimer = setInterval(async () => {
            if (!this.isAnalyzing) {
                await this.captureAndAnalyze();
            }
        }, this.options.checkInterval);
    }
    
    stopRealTimeAnalysis() {
        if (this.analysisTimer) {
            clearInterval(this.analysisTimer);
            this.analysisTimer = null;
        }
        
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.updateStatus('⚪ Stopped', 'Analysis stopped', 'text-gray-600');
    }
    
    async captureAndAnalyze() {
        if (!this.options.videoElement || !this.options.canvasElement) {
            return null;
        }
        
        try {
            this.isAnalyzing = true;
            this.updateStatus('🟡 Analyzing', 'Performing anti-spoofing check...', 'text-yellow-600');
            
            // Capture frame from video
            const canvas = this.options.canvasElement;
            const video = this.options.videoElement;
            
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);
            
            // Convert to blob
            const blob = await new Promise(resolve => {
                canvas.toBlob(resolve, 'image/jpeg', 0.8);
            });
            
            if (!blob) {
                throw new Error('Failed to capture image');
            }
            
            // Analyze with server
            const result = await this.analyzeImage(blob);
            
            // Update display
            this.updateAnalysisResults(result);
            
            // Store in history
            this.analysisHistory.push({
                timestamp: Date.now(),
                result: result
            });
            
            // Keep history size manageable
            if (this.analysisHistory.length > this.maxHistorySize) {
                this.analysisHistory.shift();
            }
            
            return result;
            
        } catch (error) {
            console.error('Analysis failed:', error);
            this.updateStatus('🔴 Error', `Analysis failed: ${error.message}`, 'text-red-600');
            return null;
        } finally {
            this.isAnalyzing = false;
        }
    }
    
    async analyzeImage(imageBlob) {
        const formData = new FormData();
        formData.append('image', imageBlob, 'capture.jpg');
        
        const response = await fetch('/api/anti-spoofing/analyze', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Analysis failed: ${response.status}`);
        }
        
        return await response.json();
    }
    
    updateAnalysisResults(result) {
        if (!result.success) {
            this.updateStatus('🔴 Failed', result.message || 'Analysis failed', 'text-red-600');
            return;
        }
        
        const isLive = result.is_live;
        const confidence = result.confidence;
        const checks = result.checks || {};
        
        // Update main status
        if (isLive && confidence >= this.options.confidenceThreshold) {
            this.updateStatus('🟢 Live Person', 'Anti-spoofing check passed', 'text-green-600');
        } else if (isLive) {
            this.updateStatus('🟡 Low Confidence', 'Confidence below threshold', 'text-yellow-600');
        } else {
            this.updateStatus('🔴 Spoofing Detected', 'Fake face detected!', 'text-red-600');
        }
        
        // Update confidence
        this.updateConfidence(confidence);
        
        // Update details
        this.updateDetails(result.details || 'Analysis complete');
        
        // Update individual checks
        this.updateChecks(checks);
    }
    
    updateStatus(status, details, className = '') {
        if (this.options.statusElement) {
            this.options.statusElement.textContent = status;
            if (className) {
                this.options.statusElement.className = `text-sm font-medium ${className}`;
            }
        }
        
        // Update indicator color
        const indicator = document.getElementById('spoofing-indicator');
        if (indicator) {
            indicator.className = `w-3 h-3 rounded-full mr-2 ${this.getIndicatorColor(status)}`;
        }
        
        if (details && this.options.detailsElement) {
            this.options.detailsElement.textContent = details;
        }
    }
    
    getIndicatorColor(status) {
        if (status.includes('🟢')) return 'bg-green-500';
        if (status.includes('🔴')) return 'bg-red-500';
        if (status.includes('🟡')) return 'bg-yellow-500';
        return 'bg-gray-500';
    }
    
    updateConfidence(confidence) {
        const percentage = Math.round(confidence * 100);
        
        if (this.options.confidenceElement) {
            this.options.confidenceElement.textContent = `${percentage}%`;
        }
        
        const confidenceBar = document.getElementById('confidence-bar');
        if (confidenceBar) {
            confidenceBar.style.width = `${percentage}%`;
            
            // Update color based on confidence level
            if (confidence >= 0.8) {
                confidenceBar.className = 'bg-green-500 h-2 rounded-full transition-all duration-300';
            } else if (confidence >= 0.5) {
                confidenceBar.className = 'bg-yellow-500 h-2 rounded-full transition-all duration-300';
            } else {
                confidenceBar.className = 'bg-red-500 h-2 rounded-full transition-all duration-300';
            }
        }
    }
    
    updateDetails(details) {
        if (this.options.detailsElement) {
            this.options.detailsElement.textContent = details;
        }
    }
    
    updateChecks(checks) {
        const checkElements = {
            'blink_detection': 'blink-check',
            'texture_analysis': 'texture-check',
            'color_analysis': 'color-check',
            'motion_analysis': 'motion-check'
        };
        
        Object.entries(checkElements).forEach(([checkName, elementId]) => {
            const element = document.getElementById(elementId);
            if (element && checks[checkName]) {
                const passed = checks[checkName].passed;
                element.className = `w-2 h-2 rounded-full mr-1 ${passed ? 'bg-green-500' : 'bg-red-500'}`;
            }
        });
    }
    
    async resetAnalysis() {
        try {
            await fetch('/api/anti-spoofing/reset', { method: 'POST' });
            this.analysisHistory = [];
            this.updateStatus('⚪ Reset', 'Analysis state reset', 'text-gray-600');
        } catch (error) {
            console.error('Reset failed:', error);
        }
    }
    
    getAnalysisHistory() {
        return this.analysisHistory;
    }
    
    isCurrentlyLive() {
        if (this.analysisHistory.length === 0) return false;
        
        const latest = this.analysisHistory[this.analysisHistory.length - 1];
        return latest.result?.is_live && 
               latest.result?.confidence >= this.options.confidenceThreshold;
    }
    
    getLatestConfidence() {
        if (this.analysisHistory.length === 0) return 0;
        
        const latest = this.analysisHistory[this.analysisHistory.length - 1];
        return latest.result?.confidence || 0;
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AntiSpoofingManager;
} else if (typeof window !== 'undefined') {
    window.AntiSpoofingManager = AntiSpoofingManager;
}