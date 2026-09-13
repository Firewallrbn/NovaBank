import { useEffect, useRef } from 'react';
import { Renderer, Program, Mesh, Triangle, Color } from 'ogl';

/**
 * Fondo WebGL de hilos paralelos que se tuercen con ruido Perlin.
 *
 * Adaptado del componente `Threads` original en tres puntos:
 *  1. Sin interacción con el mouse: es fondo, no un elemento interactivo.
 *  2. Degradado de color a lo largo del haz (verde profundo hacia verde lima)
 *     en vez de un color plano, como en la referencia visual.
 *  3. Respeta `prefers-reduced-motion`: dibuja un solo fotograma y se detiene.
 */

const vertexShader = `
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const fragmentShader = `
precision highp float;

uniform float iTime;
uniform vec3 iResolution;
uniform vec3 uColorDeep;
uniform vec3 uColorBright;
uniform float uAmplitude;
uniform float uDistance;

const int u_line_count = 40;
const float u_line_width = 7.0;
const float u_line_blur = 10.0;

float Perlin2D(vec2 P) {
    vec2 Pi = floor(P);
    vec4 Pf_Pfmin1 = P.xyxy - vec4(Pi, Pi + 1.0);
    vec4 Pt = vec4(Pi.xy, Pi.xy + 1.0);
    Pt = Pt - floor(Pt * (1.0 / 71.0)) * 71.0;
    Pt += vec2(26.0, 161.0).xyxy;
    Pt *= Pt;
    Pt = Pt.xzxz * Pt.yyww;
    vec4 hash_x = fract(Pt * (1.0 / 951.135664));
    vec4 hash_y = fract(Pt * (1.0 / 642.949883));
    vec4 grad_x = hash_x - 0.49999;
    vec4 grad_y = hash_y - 0.49999;
    vec4 grad_results = inversesqrt(grad_x * grad_x + grad_y * grad_y)
        * (grad_x * Pf_Pfmin1.xzxz + grad_y * Pf_Pfmin1.yyww);
    grad_results *= 1.4142135623730950;
    vec2 blend = Pf_Pfmin1.xy * Pf_Pfmin1.xy * Pf_Pfmin1.xy
               * (Pf_Pfmin1.xy * (Pf_Pfmin1.xy * 6.0 - 15.0) + 10.0);
    vec4 blend2 = vec4(blend, vec2(1.0 - blend));
    return dot(grad_results, blend2.zxzx * blend2.wwyy);
}

float pixel(float count, vec2 resolution) {
    return (1.0 / max(resolution.x, resolution.y)) * count;
}

float lineFn(vec2 st, float width, float perc, float time, float amplitude, float distance) {
    float split_offset = (perc * 0.4);
    float split_point = 0.1 + split_offset;

    float amplitude_normal = smoothstep(split_point, 0.7, st.x);
    float finalAmplitude = amplitude_normal * 0.5 * amplitude;

    float time_scaled = time / 10.0;
    float blur = smoothstep(split_point, split_point + 0.05, st.x) * perc;

    float xnoise = mix(
        Perlin2D(vec2(time_scaled, st.x + perc) * 2.5),
        Perlin2D(vec2(time_scaled, st.x + time_scaled) * 3.5) / 1.5,
        st.x * 0.3
    );

    float y = 0.5 + (perc - 0.5) * distance + xnoise / 2.0 * finalAmplitude;

    float line_start = smoothstep(
        y + (width / 2.0) + (u_line_blur * pixel(1.0, iResolution.xy) * blur),
        y,
        st.y
    );

    float line_end = smoothstep(
        y,
        y - (width / 2.0) - (u_line_blur * pixel(1.0, iResolution.xy) * blur),
        st.y
    );

    // El exponente decide cuántos hilos del haz siguen siendo visibles: cuanto
    // más alto, más hilos acompañan al núcleo antes de apagarse.
    return clamp(
        (line_start - line_end) * (1.0 - smoothstep(0.0, 1.0, pow(perc, 0.72))),
        0.0,
        1.0
    );
}

void main() {
    vec2 uv = gl_FragCoord.xy / iResolution.xy;

    float line_strength = 1.0;
    vec3 accumulated = vec3(0.0);
    float weight = 0.0;

    for (int i = 0; i < u_line_count; i++) {
        float p = float(i) / float(u_line_count);
        float line = lineFn(
            uv,
            u_line_width * pixel(1.0, iResolution.xy) * (1.0 - p),
            p,
            iTime,
            uAmplitude,
            uDistance
        );
        // Cada hilo toma su color según su posición en el haz: el degradado
        // recorre el haz completo en lugar de teñir todo del mismo verde.
        // Se comprime al tramo de hilos realmente visibles (p bajo).
        accumulated += mix(uColorBright, uColorDeep, clamp(p * 2.6, 0.0, 1.0)) * line;
        weight += line;
        line_strength *= (1.0 - line);
    }

    float colorVal = 1.0 - line_strength;
    vec3 tint = weight > 0.0 ? accumulated / weight : uColorDeep;
    gl_FragColor = vec4(tint * colorVal, colorVal);
}
`;

type ThreadsProps = {
  /** Color de los hilos del borde del haz. */
  colorDeep?: [number, number, number];
  /** Color de los hilos del centro del haz. */
  colorBright?: [number, number, number];
  amplitude?: number;
  distance?: number;
  /** Multiplicador del paso del tiempo: por debajo de 1 el haz ondula más despacio. */
  speed?: number;
  className?: string;
};

export default function Threads({
  colorDeep = [0.047, 0.561, 0.388],
  colorBright = [0.494, 0.941, 0.478],
  amplitude = 1,
  distance = 0.35,
  speed = 1,
  className,
}: ThreadsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Los props viven en un ref para que cambiarlos mute los uniforms en vivo
  // en lugar de reconstruir el contexto WebGL entero.
  const propsRef = useRef({ colorDeep, colorBright, amplitude, distance, speed });
  propsRef.current = { colorDeep, colorBright, amplitude, distance, speed };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const renderer = new Renderer({ alpha: true, antialias: false });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    container.appendChild(gl.canvas);
    gl.canvas.style.width = '100%';
    gl.canvas.style.height = '100%';
    gl.canvas.style.display = 'block';

    const geometry = new Triangle(gl);
    const program = new Program(gl, {
      vertex: vertexShader,
      fragment: fragmentShader,
      uniforms: {
        iTime: { value: 0 },
        iResolution: {
          value: new Color(gl.canvas.width, gl.canvas.height, gl.canvas.width / gl.canvas.height),
        },
        uColorDeep: { value: new Color(...propsRef.current.colorDeep) },
        uColorBright: { value: new Color(...propsRef.current.colorBright) },
        uAmplitude: { value: propsRef.current.amplitude },
        uDistance: { value: propsRef.current.distance },
      },
    });

    const mesh = new Mesh(gl, { geometry, program });

    // El fragment shader es pesado (ruido Perlin por pixel para 40 hilos), así que
    // su costo escala con los pixeles dibujados. Se limita la resolución interna
    // para que pantallas grandes o de alta densidad sigan fluidas; el efecto es
    // lo bastante suave como para que la reducción no se note.
    const MAX_RENDER_DIM = 1600;
    function resize() {
      if (!container) return;
      const { clientWidth, clientHeight } = container;
      if (clientWidth === 0 || clientHeight === 0) return;
      const baseDpr = Math.min(window.devicePixelRatio || 1, 2);
      const longestSide = Math.max(clientWidth, clientHeight) * baseDpr;
      renderer.dpr = longestSide > MAX_RENDER_DIM ? (baseDpr * MAX_RENDER_DIM) / longestSide : baseDpr;
      renderer.setSize(clientWidth, clientHeight);
      program.uniforms.iResolution.value.r = gl.canvas.width;
      program.uniforms.iResolution.value.g = gl.canvas.height;
      program.uniforms.iResolution.value.b = gl.canvas.width / gl.canvas.height;
      if (reduceMotion) renderer.render({ scene: mesh });
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    // Sin movimiento: un fotograma fijo y nada de bucle de animación.
    if (reduceMotion) {
      renderer.render({ scene: mesh });
      return () => {
        resizeObserver.disconnect();
        if (container.contains(gl.canvas)) container.removeChild(gl.canvas);
        gl.getExtension('WEBGL_lose_context')?.loseContext();
      };
    }

    // Solo se anima mientras el canvas está en pantalla y la pestaña visible,
    // para no quemar GPU en algo que nadie está viendo.
    let isVisible = true;
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        isVisible = entries[0].isIntersecting;
      },
      { threshold: 0 },
    );
    intersectionObserver.observe(container);

    let frameId = 0;
    function update(t: number) {
      frameId = requestAnimationFrame(update);
      if (!isVisible || document.hidden) return;

      const current = propsRef.current;
      program.uniforms.uColorDeep.value.set(...current.colorDeep);
      program.uniforms.uColorBright.value.set(...current.colorBright);
      program.uniforms.uAmplitude.value = current.amplitude;
      program.uniforms.uDistance.value = current.distance;
      program.uniforms.iTime.value = t * 0.001 * current.speed;

      renderer.render({ scene: mesh });
    }
    frameId = requestAnimationFrame(update);

    return () => {
      cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      if (container.contains(gl.canvas)) container.removeChild(gl.canvas);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    };
  }, []);

  return <div ref={containerRef} aria-hidden="true" className={className} />;
}
