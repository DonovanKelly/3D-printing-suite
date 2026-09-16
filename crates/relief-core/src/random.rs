/*! Python-compatible integer-seeded MT19937 preserves existing random puzzle patterns.
Python choice uses rejection-sampled getrandbits, while uniform uses 53-bit random(). */
pub struct PythonRandom {
    state: [u32; 624],
    index: usize,
}
impl PythonRandom {
    pub fn new(seed: u32) -> Self {
        let mut r = Self {
            state: [0; 624],
            index: 624,
        };
        r.state[0] = 19650218;
        for i in 1..624 {
            r.state[i] = 1812433253u32
                .wrapping_mul(r.state[i - 1] ^ (r.state[i - 1] >> 30))
                .wrapping_add(i as u32);
        }
        let mut i = 1;
        for _ in 0..624 {
            r.state[i] = (r.state[i]
                ^ ((r.state[i - 1] ^ (r.state[i - 1] >> 30)).wrapping_mul(1664525)))
            .wrapping_add(seed);
            i += 1;
            if i >= 624 {
                r.state[0] = r.state[623];
                i = 1;
            }
        }
        for _ in 0..623 {
            r.state[i] = (r.state[i]
                ^ ((r.state[i - 1] ^ (r.state[i - 1] >> 30)).wrapping_mul(1566083941)))
            .wrapping_sub(i as u32);
            i += 1;
            if i >= 624 {
                r.state[0] = r.state[623];
                i = 1;
            }
        }
        r.state[0] = 0x80000000;
        r
    }
    fn next(&mut self) -> u32 {
        if self.index >= 624 {
            for i in 0..624 {
                let y = (self.state[i] & 0x80000000) | (self.state[(i + 1) % 624] & 0x7fffffff);
                self.state[i] = self.state[(i + 397) % 624]
                    ^ (y >> 1)
                    ^ if y & 1 != 0 { 0x9908b0df } else { 0 };
            }
            self.index = 0;
        }
        let mut y = self.state[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^= y >> 18;
        y
    }
    pub fn uniform(&mut self, low: f64, high: f64) -> f64 {
        let a = (self.next() >> 5) as f64;
        let b = (self.next() >> 6) as f64;
        low + (high - low) * (a * 67108864.0 + b) / 9007199254740992.0
    }
    pub fn sign(&mut self) -> f64 {
        loop {
            let bits = self.next() >> 30;
            if bits < 2 {
                return if bits == 0 { -1.0 } else { 1.0 };
            }
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn python_seed_one() {
        let mut r = PythonRandom::new(1);
        assert!((r.uniform(0.0, 1.0) - 0.13436424411240122).abs() < 1e-15);
        assert!((r.uniform(0.0, 1.0) - 0.8474337369372327).abs() < 1e-15);
    }
}
