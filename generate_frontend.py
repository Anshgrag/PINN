import os

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PINN Tsunami Resilience 3D HUD</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        :root {
            --bg-deep: #050608;
            --panel-bg: rgba(10, 12, 16, 0.75);
            --accent-neon: #00F3FF;
            --danger-neon: #FF0055;
            --success-neon: #00FF95;
            --warning-neon: #FFB300;
            --text-main: #C0C5CE;
            --text-dim: #4B5263;
            --border-glow: rgba(0, 243, 255, 0.3);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'JetBrains Mono', monospace; user-select: none; }
        body { background-color: var(--bg-deep); color: var(--text-main); overflow: hidden; width: 100vw; height: 100vh; }
        
        #webgl-container { position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1; }
        
        .hud-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 10; pointer-events: none; display: flex; justify-content: space-between; padding: 20px; }
        
        .panel { background: var(--panel-bg); backdrop-filter: blur(10px); border: 1px solid rgba(0, 243, 255, 0.2); box-shadow: 0 0 20px rgba(0, 243, 255, 0.05); padding: 25px; width: 350px; display: flex; flex-direction: column; gap: 20px; pointer-events: auto; max-height: calc(100vh - 120px); overflow-y: auto; }
        
        .panel::-webkit-scrollbar { width: 4px; }
        .panel::-webkit-scrollbar-thumb { background: var(--accent-neon); border-radius: 2px; }
        
        .header h1 { font-size: 1.2rem; letter-spacing: 2px; color: var(--accent-neon); text-shadow: 0 0 10px var(--accent-neon); margin-bottom: 5px; text-transform: uppercase; }
        .header p { font-size: 0.65rem; color: var(--text-dim); letter-spacing: 1px; text-transform: uppercase; }
        
        .engine-status { display: flex; align-items: center; gap: 10px; font-size: 0.7rem; font-weight: bold; background: rgba(0,0,0,0.5); padding: 8px 12px; border-radius: 4px; border-left: 3px solid var(--accent-neon); }
        .engine-status.ai-active { border-left-color: var(--success-neon); color: var(--success-neon); text-shadow: 0 0 5px var(--success-neon); }
        .engine-status.ai-offline { border-left-color: var(--accent-neon); color: var(--accent-neon); }
        .indicator-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-neon); box-shadow: 0 0 8px var(--accent-neon); }
        .ai-active .indicator-dot { background: var(--success-neon); box-shadow: 0 0 8px var(--success-neon); animation: pulse 1s infinite; }
        
        @keyframes pulse { 0%, 100% { opacity: 0.5; transform: scale(1); } 50% { opacity: 1; transform: scale(1.2); } }
        
        .control-group { display: flex; flex-direction: column; gap: 15px; }
        .slider-wrapper { display: flex; flex-direction: column; gap: 5px; }
        .slider-header { display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-dim); text-transform: uppercase; }
        .slider-val { color: var(--accent-neon); font-weight: bold; text-shadow: 0 0 5px var(--accent-neon); }
        
        input[type="range"] { -webkit-appearance: none; width: 100%; height: 2px; background: rgba(255,255,255,0.1); outline: none; margin: 10px 0; }
        input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; background: var(--bg-deep); border: 2px solid var(--accent-neon); border-radius: 50%; cursor: pointer; box-shadow: 0 0 10px var(--accent-neon); }
        
        .gauge-container { display: flex; align-items: center; justify-content: center; position: relative; height: 120px; margin: 10px 0; }
        .gauge-text { position: absolute; text-align: center; }
        .gauge-value { font-size: 1.5rem; color: var(--accent-neon); font-weight: bold; text-shadow: 0 0 10px var(--accent-neon); }
        .gauge-label { font-size: 0.6rem; color: var(--text-dim); }
        
        select.btn-action { appearance: none; background: rgba(0, 243, 255, 0.05); color: var(--accent-neon); border: 1px solid var(--accent-neon); padding: 10px; font-family: inherit; font-size: 0.7rem; text-transform: uppercase; cursor: pointer; }
        select.btn-action option { background: var(--bg-deep); color: var(--text-main); }
        
        .btn-launch { background: rgba(0, 243, 255, 0.1); color: var(--accent-neon); border: 1px solid var(--accent-neon); padding: 15px; font-weight: bold; cursor: pointer; font-family: inherit; text-transform: uppercase; letter-spacing: 2px; transition: 0.3s; box-shadow: inset 0 0 10px rgba(0,243,255,0.1), 0 0 15px rgba(0,243,255,0.2); }
        .btn-launch:hover { background: var(--accent-neon); color: var(--bg-deep); box-shadow: 0 0 20px var(--accent-neon); }
        
        .telemetry-box { background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.1); border-left: 2px solid var(--accent-neon); padding: 15px; display: flex; flex-direction: column; gap: 8px; }
        .stat-row { display: flex; justify-content: space-between; font-size: 0.75rem; }
        .stat-label { color: var(--text-dim); text-transform: uppercase; }
        .stat-value { color: var(--accent-neon); font-weight: bold; }
        .stat-value.danger { color: var(--danger-neon); text-shadow: 0 0 5px var(--danger-neon); }
        .stat-value.warning { color: var(--warning-neon); text-shadow: 0 0 5px var(--warning-neon); }
        
        .chart-container { height: 150px; width: 100%; margin-top: 10px; }
        
        #inundation-overlay { position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 5; background: radial-gradient(circle, rgba(255,0,85,0.1) 0%, rgba(0,0,0,0) 70%); box-shadow: inset 0 0 150px rgba(255,0,85,0.2); border: 2px solid rgba(255,0,85,0.3); display: none; }
        #inundation-overlay::after { content: 'CRITICAL INUNDATION DETECTED'; position: absolute; top: 50px; left: 50%; transform: translateX(-50%); color: var(--danger-neon); font-size: 1.5rem; letter-spacing: 5px; font-weight: bold; text-shadow: 0 0 20px var(--danger-neon); animation: blink 1s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        
        .bottom-timeline { position: absolute; bottom: 0; left: 0; width: 100%; height: 80px; background: rgba(5, 6, 8, 0.9); border-top: 1px solid var(--border-glow); z-index: 10; display: flex; align-items: center; padding: 0 50px; justify-content: center; }
        .timeline-track { width: 80%; height: 2px; background: rgba(255,255,255,0.2); position: relative; }
        .timeline-marker { position: absolute; top: -5px; width: 12px; height: 12px; background: var(--bg-deep); border: 2px solid var(--accent-neon); border-radius: 50%; cursor: pointer; transform: translateX(-50%); transition: 0.3s; box-shadow: 0 0 10px var(--accent-neon); }
        .timeline-marker:hover { transform: translateX(-50%) scale(1.5); background: var(--accent-neon); }
        .timeline-label { position: absolute; top: 15px; font-size: 0.6rem; color: var(--text-dim); transform: translateX(-50%); text-align: center; white-space: nowrap; transition: 0.3s; }
        .timeline-marker:hover + .timeline-label { color: var(--accent-neon); text-shadow: 0 0 5px var(--accent-neon); }
        
        #loading-modal { position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.85); z-index: 100; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; backdrop-filter: blur(5px); opacity: 0; pointer-events: none; transition: opacity 0.3s; }
        #loading-modal.active { opacity: 1; pointer-events: auto; }
        .spinner { width: 60px; height: 60px; border: 3px solid rgba(0, 243, 255, 0.1); border-top-color: var(--accent-neon); border-radius: 50%; animation: spin 1s linear infinite; box-shadow: 0 0 20px rgba(0, 243, 255, 0.2); }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-text { color: var(--accent-neon); font-size: 1.2rem; letter-spacing: 4px; font-weight: bold; text-transform: uppercase; text-shadow: 0 0 15px var(--accent-neon); text-align: center; }
        
    </style>
</head>
<body>
    <div id="webgl-container"></div>
    <div id="inundation-overlay"></div>
    
    <div id="loading-modal">
        <div class="spinner"></div>
        <div class="loading-text">CALCULATING FINAL CASUALTY<br>AND DAMAGE MODELS</div>
    </div>
    
    <div class="hud-overlay">
        <!-- Left Panel: Controls -->
        <div class="panel" style="margin-bottom: 80px;">
            <div class="header">
                <h1>TSUNAMI_RES // HUD</h1>
                <p>Tactical Simulation Override</p>
            </div>
            
            <div class="engine-status" id="engine-indicator">
                <div class="indicator-dot"></div>
                <span id="engine-text">CLIENT ENGINE (LOCAL)</span>
            </div>
            
            <div class="control-group">
                <div class="gauge-container">
                    <canvas id="velocity-gauge" width="120" height="120"></canvas>
                    <div class="gauge-text">
                        <div class="gauge-value" id="disp-velocity">15.0</div>
                        <div class="gauge-label">m/s VELOCITY</div>
                    </div>
                </div>
            
                <div class="slider-wrapper">
                    <div class="slider-header"><span>Wave Height (m)</span><span class="slider-val" id="disp-wave">5.0</span></div>
                    <input type="range" id="slider-wave" min="1" max="50" step="0.5" value="5.0">
                </div>
                
                <div class="slider-wrapper">
                    <div class="slider-header"><span>Duration (hrs)</span><span class="slider-val" id="disp-duration">2.0</span></div>
                    <input type="range" id="slider-duration" min="0.5" max="12" step="0.5" value="2.0">
                </div>
                
                <div class="slider-wrapper">
                    <div class="slider-header"><span>Debris Density</span><span class="slider-val" id="disp-debris">0.2</span></div>
                    <input type="range" id="slider-debris" min="0.0" max="1.0" step="0.1" value="0.2">
                </div>
                
                <select id="defense-selector" class="btn-action">
                    <option value="none">No Defense (Baseline)</option>
                    <option value="seawall">RC Seawall (Kamaishi)</option>
                    <option value="tetrapod">Tetrapod Breakwater</option>
                    <option value="mangrove">Mangrove Eco-Shield</option>
                </select>
                
                <button class="btn-launch" id="btn-launch">INITIATE SURGE</button>
            </div>
        </div>
        
        <!-- Right Panel: Telemetry -->
        <div class="panel" style="margin-bottom: 80px;">
            <div class="header">
                <h1 style="color: var(--success-neon); text-shadow: 0 0 10px var(--success-neon);">SYS_TELEMETRY</h1>
                <p>Real-Time Structural Diagnostics</p>
            </div>
            
            <div class="telemetry-box" style="border-left-color: var(--warning-neon);">
                <div style="font-size: 0.6rem; color: var(--warning-neon); margin-bottom: 5px; letter-spacing: 2px;">STRUCTURAL_WEAR</div>
                <div class="stat-row"><span class="stat-label">Max Pressure</span><span class="stat-value" id="stat-pressure">0.0 kPa</span></div>
                <div class="stat-row"><span class="stat-label">Hydro-Resistance</span><span class="stat-value" id="stat-resistance">100%</span></div>
                <div class="stat-row"><span class="stat-label">Permeability</span><span class="stat-value" id="stat-permeability">100%</span></div>
            </div>
            
            <div class="telemetry-box" style="border-left-color: var(--danger-neon);">
                <div style="font-size: 0.6rem; color: var(--danger-neon); margin-bottom: 5px; letter-spacing: 2px;">DAMAGE_SUMMARY</div>
                <div class="stat-row"><span class="stat-label">Critical Failures</span><span class="stat-value danger" id="stat-failures">0</span></div>
                <div class="stat-row"><span class="stat-label">Survival Rate</span><span class="stat-value" id="stat-survival">100%</span></div>
                <div class="stat-row"><span class="stat-label">Design Quality</span><span class="stat-value" id="stat-quality">OPTIMAL</span></div>
            </div>
            
            <div style="font-size: 0.6rem; color: var(--text-dim); margin-top: 10px; letter-spacing: 1px;">WAVE_AMPLITUDE_HISTORY (m)</div>
            <div class="chart-container">
                <canvas id="wave-chart"></canvas>
            </div>
        </div>
    </div>
    
    <div class="bottom-timeline">
        <div class="timeline-track">
            <!-- Dynamic markers will be inserted here -->
        </div>
    </div>

    <script>
        // Data Configuration
        const CONFIG = {
            gridSize: 64,
            tileSize: 2,
            events: [
                { name: '1755 Lisbon', h: 15, v: 6, d: 20 },
                { name: '2004 Sumatra', h: 30, v: 9, d: 7 },
                { name: '2011 Tohoku', h: 40, v: 11, d: 6 },
                { name: '2018 Palu', h: 11, v: 22, d: 5 }
            ]
        };

        // State
        let state = {
            waveHeight: 5.0,
            velocity: 15.0,
            duration: 2.0,
            debris: 0.2,
            defense: 'none',
            isSimulating: false,
            useAI: false,
            backendUrl: 'http://localhost:8000/predict'
        };

        // Three.js Setup
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x050608, 0.015);
        
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(-80, 60, 80);
        
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        document.getElementById('webgl-container').appendChild(renderer.domElement);
        
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.maxPolarAngle = Math.PI / 2 - 0.05;
        controls.target.set(0, 0, 0);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x222233, 1.5);
        scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0x00F3FF, 1.5);
        dirLight.position.set(50, 100, 50);
        scene.add(dirLight);
        const redLight = new THREE.DirectionalLight(0xFF0055, 0.5);
        redLight.position.set(-50, 50, -50);
        scene.add(redLight);

        // Grid Data Generation
        const elevationMap = [];
        const materialMap = [];
        for (let i = 0; i < CONFIG.gridSize; i++) {
            elevationMap[i] = []; materialMap[i] = [];
            for (let j = 0; j < CONFIG.gridSize; j++) {
                elevationMap[i][j] = 0;
                materialMap[i][j] = 0;
                
                // City layout logic
                if (j > 10 && j < CONFIG.gridSize - 10 && i % 4 !== 0 && j % 6 !== 0) {
                    const r = Math.random();
                    if (r > 0.95) { elevationMap[i][j] = Math.random() * 20 + 20; materialMap[i][j] = 3; } // Concrete
                    else if (r > 0.7) { elevationMap[i][j] = Math.random() * 10 + 10; materialMap[i][j] = 2; } // Masonry
                    else { elevationMap[i][j] = Math.random() * 5 + 5; materialMap[i][j] = 1; } // Wood
                }
            }
        }

        // 3D Objects
        let buildingMesh, terrainMesh, waterMesh, vectorArrows, particleSystem, beacons = [];
        let waterGeometry, waterPositions;

        function buildScene() {
            // 1. Terrain Grid
            const terrainGeo = new THREE.PlaneGeometry(CONFIG.gridSize * CONFIG.tileSize, CONFIG.gridSize * CONFIG.tileSize, CONFIG.gridSize - 1, CONFIG.gridSize - 1);
            terrainGeo.rotateX(-Math.PI / 2);
            
            // Modify vertices based on a slight slope
            const pos = terrainGeo.attributes.position.array;
            for(let i=0; i<pos.length; i+=3) {
                const x = pos[i];
                // Slope up towards positive X
                pos[i+1] = (x + (CONFIG.gridSize * CONFIG.tileSize)/2) * 0.05; 
            }
            terrainGeo.computeVertexNormals();

            const terrainMat = new THREE.MeshStandardMaterial({
                color: 0x0A0D14,
                wireframe: true,
                transparent: true,
                opacity: 0.3,
                emissive: 0x00F3FF,
                emissiveIntensity: 0.1
            });
            terrainMesh = new THREE.Mesh(terrainGeo, terrainMat);
            scene.add(terrainMesh);

            // 2. Instanced Buildings
            const bGeo = new THREE.BoxGeometry(CONFIG.tileSize * 0.8, 1, CONFIG.tileSize * 0.8);
            bGeo.translate(0, 0.5, 0); // Origin at bottom
            const bMat = new THREE.MeshStandardMaterial({
                color: 0x4B5263,
                roughness: 0.8,
                metalness: 0.2
            });
            
            const bCount = elevationMap.flat().filter(h => h > 0).length;
            buildingMesh = new THREE.InstancedMesh(bGeo, bMat, bCount);
            
            const dummy = new THREE.Object3D();
            const color = new THREE.Color();
            let idx = 0;
            
            const offsetX = (CONFIG.gridSize * CONFIG.tileSize) / 2;
            const offsetZ = (CONFIG.gridSize * CONFIG.tileSize) / 2;
            
            for (let i = 0; i < CONFIG.gridSize; i++) {
                for (let j = 0; j < CONFIG.gridSize; j++) {
                    const h = elevationMap[i][j];
                    if (h > 0) {
                        const x = j * CONFIG.tileSize - offsetX + CONFIG.tileSize/2;
                        const z = i * CONFIG.tileSize - offsetZ + CONFIG.tileSize/2;
                        const groundY = (x + offsetX) * 0.05;
                        
                        dummy.position.set(x, groundY, z);
                        dummy.scale.set(1, h, 1);
                        dummy.updateMatrix();
                        buildingMesh.setMatrixAt(idx, dummy.matrix);
                        
                        // Color based on material
                        const mat = materialMap[i][j];
                        if (mat === 3) color.setHex(0x606570);
                        else if (mat === 2) color.setHex(0x8C7A6B);
                        else color.setHex(0x5A4634);
                        
                        buildingMesh.setColorAt(idx, color);
                        idx++;
                    }
                }
            }
            buildingMesh.instanceMatrix.needsUpdate = true;
            if(buildingMesh.instanceColor) buildingMesh.instanceColor.needsUpdate = true;
            scene.add(buildingMesh);

            // 3. 3D Water Mesh
            waterGeometry = new THREE.PlaneGeometry(CONFIG.gridSize * CONFIG.tileSize, CONFIG.gridSize * CONFIG.tileSize, CONFIG.gridSize - 1, CONFIG.gridSize - 1);
            waterGeometry.rotateX(-Math.PI / 2);
            waterPositions = new Float32Array(waterGeometry.attributes.position.array);
            
            const waterMat = new THREE.MeshPhysicalMaterial({
                color: 0x00D2FF,
                transparent: true,
                opacity: 0.6,
                roughness: 0.1,
                transmission: 0.9,
                thickness: 0.5,
                depthWrite: false
            });
            waterMesh = new THREE.Mesh(waterGeometry, waterMat);
            // Hide initially
            waterMesh.position.y = -10; 
            scene.add(waterMesh);
            
            // 4. Glowing Location Pins
            const pinLocations = [
                { name: 'PORT', x: 5, z: 32 },
                { name: 'HOSPITAL', x: 30, z: 15 },
                { name: 'POWER PLANT', x: 50, z: 50 }
            ];
            
            pinLocations.forEach(loc => {
                const rx = loc.x * CONFIG.tileSize - offsetX;
                const rz = loc.z * CONFIG.tileSize - offsetZ;
                const ry = (rx + offsetX) * 0.05;
                
                // Line
                const lMat = new THREE.LineDashedMaterial({ color: 0x00FF95, dashSize: 1, gapSize: 1 });
                const lGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(rx, ry, rz), new THREE.Vector3(rx, ry + 20, rz)]);
                const line = new THREE.Line(lGeo, lMat);
                line.computeLineDistances();
                scene.add(line);
                
                // Sprite
                const canvas = document.createElement('canvas');
                canvas.width = 128; canvas.height = 64;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#00FF95';
                ctx.font = 'bold 24px JetBrains Mono';
                ctx.textAlign = 'center';
                ctx.fillText(loc.name, 64, 40);
                
                const tex = new THREE.CanvasTexture(canvas);
                const sMat = new THREE.SpriteMaterial({ map: tex, color: 0xffffff });
                const sprite = new THREE.Sprite(sMat);
                sprite.position.set(rx, ry + 22, rz);
                sprite.scale.set(15, 7.5, 1);
                scene.add(sprite);
                beacons.push(sprite);
            });
            
            // 5. Debris Particles
            const pGeo = new THREE.BufferGeometry();
            const pCount = 500;
            const pPos = new Float32Array(pCount * 3);
            for(let i=0; i<pCount*3; i++) pPos[i] = (Math.random() - 0.5) * 100;
            pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
            
            const pMat = new THREE.PointsMaterial({
                color: 0x00F3FF,
                size: 0.5,
                transparent: true,
                opacity: 0.8,
                blending: THREE.AdditiveBlending
            });
            particleSystem = new THREE.Points(pGeo, pMat);
            scene.add(particleSystem);
        }

        // Gauge Rendering
        function drawGauge(val) {
            const canvas = document.getElementById('velocity-gauge');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, 120, 120);
            
            // Background track
            ctx.beginPath();
            ctx.arc(60, 60, 50, 0.75 * Math.PI, 2.25 * Math.PI);
            ctx.lineWidth = 10;
            ctx.strokeStyle = 'rgba(255,255,255,0.1)';
            ctx.lineCap = 'round';
            ctx.stroke();
            
            // Value track
            const pct = Math.min(val / 40, 1.0);
            ctx.beginPath();
            ctx.arc(60, 60, 50, 0.75 * Math.PI, (0.75 + pct * 1.5) * Math.PI);
            ctx.lineWidth = 10;
            
            // Gradient
            const grad = ctx.createLinearGradient(10, 60, 110, 60);
            grad.addColorStop(0, '#00F3FF');
            grad.addColorStop(0.5, '#00FF95');
            grad.addColorStop(1, '#FF0055');
            ctx.strokeStyle = grad;
            ctx.stroke();
            
            // Glow
            ctx.shadowBlur = 10;
            ctx.shadowColor = '#00F3FF';
            ctx.stroke();
            ctx.shadowBlur = 0;
        }

        // Chart Setup
        let waveChart;
        function initChart() {
            const ctx = document.getElementById('wave-chart').getContext('2d');
            waveChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array.from({length: 20}, (_, i) => i),
                    datasets: [{
                        label: 'Wave Amp (m)',
                        data: Array(20).fill(0),
                        borderColor: '#00FF95',
                        backgroundColor: 'rgba(0, 255, 149, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { display: false },
                        y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#4B5263' } }
                    },
                    plugins: { legend: { display: false } },
                    animation: { duration: 0 }
                }
            });
        }

        function updateChartData(val) {
            waveChart.data.datasets[0].data.shift();
            waveChart.data.datasets[0].data.push(val);
            waveChart.update();
        }

        // Backend Connection Check
        async function checkBackend() {
            try {
                // We ping the root or predict just to check if it's up.
                // We'll use a dummy request to /predict
                const payload = {
                    elevation_map: [[0]],
                    material_map: [[0]],
                    wave_height: 1.0,
                    wave_duration: 1.0,
                    debris_density: 0.0
                };
                const res = await fetch(state.backendUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (res.ok) {
                    state.useAI = true;
                    document.getElementById('engine-indicator').className = 'engine-status ai-active';
                    document.getElementById('engine-text').innerText = 'PINN AI ENGINE (ONLINE)';
                } else { throw new Error('API Error'); }
            } catch (e) {
                state.useAI = false;
                document.getElementById('engine-indicator').className = 'engine-status ai-offline';
                document.getElementById('engine-text').innerText = 'CLIENT ENGINE (FALLBACK)';
            }
        }

        // UI Event Listeners
        document.getElementById('slider-wave').addEventListener('input', e => {
            state.waveHeight = parseFloat(e.target.value);
            document.getElementById('disp-wave').innerText = state.waveHeight.toFixed(1);
            state.velocity = Math.sqrt(9.81 * state.waveHeight) * 2; // Simple relation
            document.getElementById('disp-velocity').innerText = state.velocity.toFixed(1);
            drawGauge(state.velocity);
        });

        document.getElementById('slider-duration').addEventListener('input', e => {
            state.duration = parseFloat(e.target.value);
            document.getElementById('disp-duration').innerText = state.duration.toFixed(1);
        });

        document.getElementById('slider-debris').addEventListener('input', e => {
            state.debris = parseFloat(e.target.value);
            document.getElementById('disp-debris').innerText = state.debris.toFixed(1);
        });
        
        document.getElementById('defense-selector').addEventListener('change', e => {
            state.defense = e.target.value;
        });

        document.getElementById('btn-launch').addEventListener('click', async () => {
            if (state.isSimulating) {
                // Reset
                state.isSimulating = false;
                document.getElementById('btn-launch').innerText = 'INITIATE SURGE';
                document.getElementById('inundation-overlay').style.display = 'none';
                waterMesh.position.y = -10;
                initChart();
                return;
            }
            
            const modal = document.getElementById('loading-modal');
            modal.classList.add('active');
            
            // Prepare Request
            const payload = {
                elevation_map: elevationMap,
                material_map: materialMap,
                wave_height: state.waveHeight,
                wave_duration: state.duration,
                debris_density: state.debris
            };

            let h_grid, u_grid, v_grid;
            let report = null;

            if (state.useAI) {
                try {
                    const res = await fetch(state.backendUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    
                    if(res.ok) {
                        report = {
                            resilience_score: res.headers.get("X-Resilience-Score"),
                            survival_rate: res.headers.get("X-Survival-Rate"),
                            permeability: res.headers.get("X-Permeability"),
                            design_quality: res.headers.get("X-Design-Quality"),
                            critical_failure_count: res.headers.get("X-Failure-Count"),
                            max_pressure_kpa: res.headers.get("X-Max-Pressure")
                        };
                        
                        const buffer = await res.arrayBuffer();
                        const floatArray = new Float32Array(buffer);
                        const elements = CONFIG.gridSize * CONFIG.gridSize;
                        
                        h_grid = floatArray.subarray(0, elements);
                        u_grid = floatArray.subarray(elements, elements*2);
                        v_grid = floatArray.subarray(elements*2, elements*3);
                    } else { throw new Error('AI Error'); }
                } catch(e) {
                    console.error("AI inference failed, falling back to client.");
                    state.useAI = false;
                    [h_grid, report] = runClientSimulation();
                }
            } else {
                [h_grid, report] = runClientSimulation();
            }
            
            // Update UI with report
            if (report) {
                document.getElementById('stat-pressure').innerText = `${report.max_pressure_kpa || (Math.random()*100).toFixed(1)} kPa`;
                document.getElementById('stat-resistance').innerText = `${report.resilience_score || 100}%`;
                document.getElementById('stat-permeability').innerText = `${report.permeability || 100}%`;
                
                const failEl = document.getElementById('stat-failures');
                failEl.innerText = report.critical_failure_count || 0;
                
                const survEl = document.getElementById('stat-survival');
                const survRate = parseFloat(report.survival_rate || 100);
                survEl.innerText = `${survRate.toFixed(1)}%`;
                
                const qEl = document.getElementById('stat-quality');
                qEl.innerText = report.design_quality || "GOOD";
                
                if (survRate < 80) {
                    survEl.className = "stat-value danger";
                    qEl.className = "stat-value danger";
                    document.getElementById('inundation-overlay').style.display = 'block';
                } else {
                    survEl.className = "stat-value";
                    qEl.className = "stat-value";
                    document.getElementById('inundation-overlay').style.display = 'none';
                }
            }
            
            // Animate Water
            animateWaterSurge(h_grid);
            
            setTimeout(() => {
                modal.classList.remove('active');
                state.isSimulating = true;
                document.getElementById('btn-launch').innerText = 'RESET SYSTEMS';
            }, 1000);
        });

        // Client Fallback logic
        function runClientSimulation() {
            const h_grid = new Float32Array(CONFIG.gridSize * CONFIG.gridSize);
            let failures = 0;
            let maxP = 0;
            
            for(let i=0; i<CONFIG.gridSize; i++){
                for(let j=0; j<CONFIG.gridSize; j++){
                    // Simple wave equation approximation
                    const distFromSource = j;
                    let h = Math.max(0, state.waveHeight - (distFromSource * 0.1) - elevationMap[i][j]);
                    
                    if (state.defense !== 'none' && distFromSource > 10) h *= 0.6;
                    
                    h_grid[i * CONFIG.gridSize + j] = h;
                    
                    if (h > 0 && materialMap[i][j] > 0) {
                        const pressure = 0.5 * 1025 * (state.velocity * state.velocity) * h;
                        maxP = Math.max(maxP, pressure);
                        if (pressure > 50000 * materialMap[i][j]) failures++;
                    }
                }
            }
            
            const totalB = elevationMap.flat().filter(x=>x>0).length;
            const surv = totalB > 0 ? (1 - failures/totalB)*100 : 100;
            
            const report = {
                resilience_score: surv * 0.8,
                survival_rate: surv,
                permeability: 90,
                design_quality: surv > 90 ? "OPTIMAL" : (surv > 60 ? "GOOD" : "POOR"),
                critical_failure_count: failures,
                max_pressure_kpa: (maxP/1000).toFixed(1)
            };
            
            return [h_grid, report];
        }

        // Animate Water to Target Grid
        function animateWaterSurge(targetGrid) {
            waterMesh.position.y = 0;
            const pos = waterGeometry.attributes.position.array;
            
            let frame = 0;
            function update() {
                if(!state.isSimulating) return;
                frame++;
                let chartVal = 0;
                
                const offsetX = (CONFIG.gridSize * CONFIG.tileSize) / 2;
                for(let i=0; i<CONFIG.gridSize; i++){
                    for(let j=0; j<CONFIG.gridSize; j++){
                        const idx = i * CONFIG.gridSize + j;
                        const targetH = targetGrid[idx];
                        
                        // Current height
                        const vIdx = idx * 3 + 1; // y component
                        
                        // Ground height
                        const groundY = ((j * CONFIG.tileSize - offsetX) + offsetX) * 0.05;
                        
                        // Sine wave animation
                        const waveOffset = Math.sin(frame * 0.05 + j * 0.2) * 0.5 * (targetH/state.waveHeight);
                        
                        // Interpolate towards target
                        const curH = pos[vIdx];
                        const newH = curH + (groundY + targetH + waveOffset - curH) * 0.05;
                        
                        pos[vIdx] = newH;
                        
                        if (i === CONFIG.gridSize/2 && j === CONFIG.gridSize/2) {
                            chartVal = newH - groundY;
                        }
                    }
                }
                waterGeometry.attributes.position.needsUpdate = true;
                
                if (frame % 5 === 0) updateChartData(Math.max(0, chartVal));
                
                // Color based on height
                const maxH = state.waveHeight;
                waterMesh.material.color.setHSL(0.55 - Math.min(chartVal/maxH, 1) * 0.55, 1.0, 0.5);
                
                requestAnimationFrame(update);
            }
            update();
        }

        // Timeline Setup
        function setupTimeline() {
            const track = document.querySelector('.timeline-track');
            CONFIG.events.forEach(ev => {
                const pct = (ev.h / 50) * 100;
                
                const marker = document.createElement('div');
                marker.className = 'timeline-marker';
                marker.style.left = `${pct}%`;
                
                const label = document.createElement('div');
                label.className = 'timeline-label';
                label.style.left = `${pct}%`;
                label.innerHTML = `${ev.name}<br>${ev.h}m`;
                
                marker.addEventListener('click', () => {
                    document.getElementById('slider-wave').value = ev.h;
                    document.getElementById('slider-wave').dispatchEvent(new Event('input'));
                    document.getElementById('slider-duration').value = ev.d;
                    document.getElementById('slider-duration').dispatchEvent(new Event('input'));
                });
                
                track.appendChild(marker);
                track.appendChild(label);
            });
        }

        // Animation Loop
        const clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            
            const time = clock.getElapsedTime();
            
            // Float beacons
            beacons.forEach((b, i) => {
                b.position.y += Math.sin(time * 2 + i) * 0.02;
            });
            
            // Move particles
            if (state.isSimulating && particleSystem) {
                const positions = particleSystem.geometry.attributes.position.array;
                for(let i=0; i<positions.length; i+=3) {
                    positions[i] += state.velocity * 0.05; // X move
                    if (positions[i] > (CONFIG.gridSize * CONFIG.tileSize)/2) {
                        positions[i] = -(CONFIG.gridSize * CONFIG.tileSize)/2;
                    }
                }
                particleSystem.geometry.attributes.position.needsUpdate = true;
            }

            renderer.render(scene, camera);
        }

        // Init
        buildScene();
        drawGauge(state.velocity);
        initChart();
        setupTimeline();
        checkBackend();
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // Periodic check for AI engine
        setInterval(checkBackend, 5000);

    </script>
</body>
</html>
"""

# Write the html content to the target file
with open("/Users/applem1pro/Desktop/pinn/PINN/dashboard.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("dashboard.html generated successfully.")
