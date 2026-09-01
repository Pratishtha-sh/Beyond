import { ArrowRight } from 'lucide-react';
import { useState, useRef, useId, useEffect } from 'react';

import rajasthanImg from '../data/images/rajasthan/rajasthan.jpg';
import kerelaImg from '../data/images/kerela.jpg';
import kashmirImg from '../data/images/Kashmir/kashmir.jpg';
import meghalayaImg from '../data/images/meghalaya.jpg';
import himachalImg from '../data/images/himachal.jpg';
import goaImg from '../data/images/Goa/goa.avif';

interface SlideData {
  title: string;
  button: string;
  src: string;
}

interface SlideProps {
  slide: SlideData;
  index: number;
  current: number;
  handleSlideClick: (index: number) => void;
  onPlanTrip?: (destinationName: string) => void;
}

const Slide = ({ slide, index, current, handleSlideClick, onPlanTrip }: SlideProps) => {
  const slideRef = useRef<HTMLLIElement>(null);
  const xRef = useRef(0);
  const yRef = useRef(0);
  const frameRef = useRef<number>();

  useEffect(() => {
    const animate = () => {
      if (!slideRef.current) return;
      slideRef.current.style.setProperty('--x', `${xRef.current}px`);
      slideRef.current.style.setProperty('--y', `${yRef.current}px`);
      frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, []);

  const handleMouseMove = (event: React.MouseEvent) => {
    const el = slideRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    xRef.current = event.clientX - (r.left + Math.floor(r.width / 2));
    yRef.current = event.clientY - (r.top + Math.floor(r.height / 2));
  };

  const handleMouseLeave = () => {
    xRef.current = 0;
    yRef.current = 0;
  };

  const imageLoaded = (event: React.SyntheticEvent<HTMLImageElement>) => {
    event.currentTarget.style.opacity = '1';
  };

  const { src, button, title } = slide;

  return (
    <li
      ref={slideRef}
      className="flex flex-col items-center justify-center relative text-center text-white opacity-100 transition-all duration-300 ease-in-out z-10 cursor-pointer select-none"
      style={{
        width: '70vmin',
        height: '70vmin',
        margin: '0 4vmin',
        perspective: '1200px',
        transformStyle: 'preserve-3d',
        transform:
          current !== index
            ? 'scale(0.98) rotateX(8deg)'
            : 'scale(1) rotateX(0deg)',
        transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        transformOrigin: 'bottom',
        listStyle: 'none',
        pointerEvents: 'auto',
      }}
      onClick={() => handleSlideClick(index)}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div
        className="absolute top-0 left-0 w-full h-full rounded-2xl overflow-hidden transition-all duration-150 ease-out"
        style={{
          backgroundColor: '#1D1F2F',
          transform:
            current === index
              ? 'translate3d(calc(var(--x) / 30), calc(var(--y) / 30), 0)'
              : 'none',
        }}
      >
        <img
          className="absolute inset-0 object-cover transition-opacity duration-500 ease-in-out"
          style={{
            width: '120%',
            height: '120%',
            opacity: current === index ? 1 : 0.5,
          }}
          alt={title}
          src={src}
          onLoad={imageLoaded}
          loading="eager"
          decoding="sync"
        />
        {current === index && (
          <div
            className="absolute inset-0 transition-all duration-1000"
            style={{ background: 'rgba(0,0,0,0.3)' }}
          />
        )}
      </div>

      <article
        className={`relative transition-opacity duration-1000 ease-in-out ${
          current === index ? 'opacity-100 visible' : 'opacity-0 invisible'
        }`}
        style={{ padding: '4vmin' }}
      >
        <h2 className="text-lg md:text-2xl lg:text-4xl font-semibold relative font-serif">
          {title}
        </h2>
        <div className="flex justify-center">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPlanTrip?.(title);
            }}
            className="mt-6 px-4 py-2 w-fit mx-auto text-sm font-medium rounded-2xl transition duration-200 cursor-pointer border-0 hover:scale-105"
            style={{
              backgroundColor: '#f9c6d0',
              color: '#2d5a47',
              height: '48px',
              boxShadow:
                '0px 2px 3px -1px rgba(0,0,0,0.1), 0px 1px 0px 0px rgba(25,28,33,0.02), 0px 0px 0px 1px rgba(25,28,33,0.08)',
            }}
          >
            {button}
          </button>
        </div>
      </article>
    </li>
  );
};

interface CarouselControlProps {
  type: string;
  title: string;
  handleClick: () => void;
}

const CarouselControl = ({ type, title, handleClick }: CarouselControlProps) => {
  return (
    <button
      className={`w-10 h-10 flex items-center mx-2 justify-center rounded-full border-0 cursor-pointer transition duration-200 hover:-translate-y-0.5 active:translate-y-0.5`}
      style={{
        backgroundColor: 'rgba(255,255,255,0.85)',
        transform: type === 'previous' ? 'rotate(180deg)' : undefined,
      }}
      title={title}
      onClick={handleClick}
    >
      <ArrowRight size={20} color="#2d5a47" />
    </button>
  );
};

interface CarouselProps {
  slides?: SlideData[];
  onPlanTrip?: (destinationName: string) => void;
}

const defaultSlides: SlideData[] = [
  { title: 'Rajasthan', button: 'Plan This Trip', src: rajasthanImg },
  { title: 'Kerala', button: 'Plan This Trip', src: kerelaImg },
  { title: 'Kashmir', button: 'Plan This Trip', src: kashmirImg },
  { title: 'Meghalaya', button: 'Plan This Trip', src: meghalayaImg },
  { title: 'Himachal', button: 'Plan This Trip', src: himachalImg },
  { title: 'Goa', button: 'Plan This Trip', src: goaImg },
];

export default function Carousel({ slides = defaultSlides, onPlanTrip }: CarouselProps) {
  const N = slides.length;
  // Triple slides array for infinite visual loop
  const extendedSlides = [...slides, ...slides, ...slides];

  const [current, setCurrent] = useState(N);
  const [hasTransition, setHasTransition] = useState(true);

  const handlePreviousClick = () => {
    if (!hasTransition) return;
    setCurrent((prev) => prev - 1);
  };

  const handleNextClick = () => {
    if (!hasTransition) return;
    setCurrent((prev) => prev + 1);
  };

  const handleSlideClick = (index: number) => {
    if (!hasTransition) return;
    const targetRealIndex = index % N;
    const currentBlock = Math.floor(current / N);
    setCurrent(currentBlock * N + targetRealIndex);
  };

  const handleTransitionEnd = () => {
    if (current < N) {
      setHasTransition(false);
      setCurrent(current + N);
    } else if (current >= 2 * N) {
      setHasTransition(false);
      setCurrent(current - N);
    }
  };

  useEffect(() => {
    if (!hasTransition) {
      const timer = setTimeout(() => {
        setHasTransition(true);
      }, 30);
      return () => clearTimeout(timer);
    }
  }, [hasTransition]);

  const id = useId();

  return (
    <div
      className="relative mx-auto"
      style={{ width: '70vmin', height: '70vmin' }}
      aria-labelledby={`carousel-heading-${id}`}
    >
      <ul
        className="absolute flex p-0 m-0"
        onTransitionEnd={handleTransitionEnd}
        style={{
          marginLeft: '-4vmin',
          marginRight: '-4vmin',
          transform: `translateX(-${current * (100 / extendedSlides.length)}%)`,
          transition: hasTransition ? 'transform 800ms cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
          pointerEvents: 'none',
        }}
      >
        {extendedSlides.map((slide, index) => (
          <Slide
            key={index}
            slide={slide}
            index={index}
            current={current}
            handleSlideClick={handleSlideClick}
            onPlanTrip={onPlanTrip}
          />
        ))}
      </ul>

      {/* Left arrow */}
      <div className="absolute -left-4 sm:-left-12 md:-left-16 top-1/2 -translate-y-1/2 z-30" style={{ pointerEvents: 'auto' }}>
        <CarouselControl
          type="previous"
          title="Go to previous slide"
          handleClick={handlePreviousClick}
        />
      </div>

      {/* Right arrow */}
      <div className="absolute -right-4 sm:-right-12 md:-right-16 top-1/2 -translate-y-1/2 z-30" style={{ pointerEvents: 'auto' }}>
        <CarouselControl
          type="next"
          title="Go to next slide"
          handleClick={handleNextClick}
        />
      </div>
    </div>
  );
}
