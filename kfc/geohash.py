import math

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


class Geohash:
    @staticmethod
    def encode(lat: float, lon: float, precision: int) -> str:
        if lat is None or lon is None or precision is None:
            raise ValueError("Invalid geohash")

        lat_min, lat_max = -90.0, 90.0
        lon_min, lon_max = -180.0, 180.0

        geohash = ""
        idx = 0
        bit = 0
        even_bit = True

        while len(geohash) < precision:
            if even_bit:
                lon_mid = (lon_min + lon_max) / 2
                if lon >= lon_mid:
                    idx = (idx << 1) | 1
                    lon_min = lon_mid
                else:
                    idx <<= 1
                    lon_max = lon_mid
            else:
                lat_mid = (lat_min + lat_max) / 2
                if lat >= lat_mid:
                    idx = (idx << 1) | 1
                    lat_min = lat_mid
                else:
                    idx <<= 1
                    lat_max = lat_mid

            even_bit = not even_bit
            bit += 1

            if bit == 5:
                geohash += BASE32[idx]
                bit = 0
                idx = 0

        return geohash

    @staticmethod
    def decode(geohash: str) -> dict:
        bounds = Geohash.bounds(geohash)

        lat_min = bounds["sw"]["lat"]
        lon_min = bounds["sw"]["lon"]
        lat_max = bounds["ne"]["lat"]
        lon_max = bounds["ne"]["lon"]

        lat = (lat_min + lat_max) / 2
        lon = (lon_min + lon_max) / 2

        lat = round(lat, max(0, int(2 - math.log10(lat_max - lat_min))))
        lon = round(lon, max(0, int(2 - math.log10(lon_max - lon_min))))

        return {"lat": lat, "lon": lon}

    @staticmethod
    def bounds(geohash: str) -> dict:
        if not geohash:
            raise ValueError("Invalid geohash")

        geohash = geohash.lower()
        even_bit = True

        lat_min, lat_max = -90.0, 90.0
        lon_min, lon_max = -180.0, 180.0

        for ch in geohash:
            idx = BASE32.find(ch)
            if idx == -1:
                raise ValueError("Invalid geohash")

            for n in range(4, -1, -1):
                bit = (idx >> n) & 1
                if even_bit:
                    lon_mid = (lon_min + lon_max) / 2
                    if bit:
                        lon_min = lon_mid
                    else:
                        lon_max = lon_mid
                else:
                    lat_mid = (lat_min + lat_max) / 2
                    if bit:
                        lat_min = lat_mid
                    else:
                        lat_max = lat_mid
                even_bit = not even_bit

        return {
            "sw": {"lat": lat_min, "lon": lon_min},
            "ne": {"lat": lat_max, "lon": lon_max},
        }
