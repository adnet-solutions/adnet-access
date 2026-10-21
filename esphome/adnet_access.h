// adnet-access: Hilfsfunktionen fuer die ESPHome-Firmware der Haustuer-Tastatur.
//  - pin_hmac(): PIN niemals im Klartext versenden/speichern, sondern HMAC-SHA256(Schluessel, PIN)
//  - Offline-Liste: Kopie der Berechtigungen, damit die Tuer auch ohne Add-on/HA oeffnet
//
// Format der Offline-Liste (vom Add-on erzeugt, max. 1800 Zeichen):
//   Eintraege getrennt durch ';'
//   K:<uid>|<maske42hex>|<gueltig_bis_tag_hex>          Karte allein genuegt
//   P:<pinhash32>|<maske42hex>|<gueltig_bis_tag_hex>     PIN allein genuegt
//   C:<uid>,<pinhash32>|<maske42hex>|<gueltig_bis_tag_hex>  Karte + PIN
//   Maske: 168 Bit = Mo 00-01 Uhr ... So 23-24 Uhr, als 42 Hex-Zeichen (Bit 0 = MSB des ersten Zeichens)
//   gueltig_bis: Tage seit 1970-01-01, ffff = unbegrenzt
#pragma once
#include <string>
#include <cstring>
#include <cstdio>
#include "mbedtls/md.h"

namespace adnet {

inline std::string pin_hmac(const std::string &key, const std::string &pin) {
  unsigned char out[32];
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_hmac(info, reinterpret_cast<const unsigned char *>(key.data()), key.size(),
                  reinterpret_cast<const unsigned char *>(pin.data()), pin.size(), out);
  char hex[33];
  for (int i = 0; i < 16; i++) snprintf(hex + 2 * i, 3, "%02x", out[i]);
  hex[32] = 0;
  return std::string(hex);  // erste 128 Bit, identisch mit security.pin_hash() im Add-on
}

inline int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

// wochenstunde: 0..167 (Mo 0 Uhr = 0)
inline bool mask_allows(const std::string &mask, int wochenstunde) {
  if (mask.size() != 42 || wochenstunde < 0 || wochenstunde > 167) return false;
  int v = hexval(mask[wochenstunde / 4]);
  if (v < 0) return false;
  return (v >> (3 - (wochenstunde % 4))) & 1;
}

// typ: 'K' (Karte), 'P' (PIN), 'C' (Karte+PIN). Liefert true, wenn ein passender, gueltiger Eintrag existiert.
inline bool offline_check(const char *liste, char typ, const std::string &uid, const std::string &pinhash,
                          int wochenstunde, long tag_heute) {
  std::string all(liste);
  size_t pos = 0;
  while (pos < all.size()) {
    size_t end = all.find(';', pos);
    if (end == std::string::npos) end = all.size();
    std::string e = all.substr(pos, end - pos);
    pos = end + 1;
    if (e.size() < 4 || e[1] != ':' || e[0] != typ) continue;
    size_t p1 = e.find('|', 2), p2 = (p1 == std::string::npos) ? p1 : e.find('|', p1 + 1);
    if (p1 == std::string::npos || p2 == std::string::npos) continue;
    std::string id = e.substr(2, p1 - 2), mask = e.substr(p1 + 1, p2 - p1 - 1);
    long bis = strtol(e.substr(p2 + 1).c_str(), nullptr, 16);
    if (bis != 0 && tag_heute > bis) continue;
    if (!mask_allows(mask, wochenstunde)) continue;
    if (typ == 'K' && id == uid) return true;
    if (typ == 'P' && id == pinhash) return true;
    if (typ == 'C' && id == uid + "," + pinhash) return true;
  }
  return false;
}

// Gibt es zu dieser Karte einen Karte+PIN-Eintrag? (dann auf PIN warten)
inline bool offline_needs_pin(const char *liste, const std::string &uid) {
  std::string all(liste), needle = "C:" + uid + ",";
  return all.find(needle) != std::string::npos;
}

// ---------- Shelly Gen2+/Gen4: HTTP-Digest-Anmeldung (SHA-256, RFC 7616) fuer den Offline-Modus ----------
inline std::string sha256_hex(const std::string &in) {
  unsigned char out[32];
  mbedtls_md(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), reinterpret_cast<const unsigned char *>(in.data()),
             in.size(), out);
  char hex[65];
  for (int i = 0; i < 32; i++) snprintf(hex + 2 * i, 3, "%02x", out[i]);
  hex[64] = 0;
  return std::string(hex);
}

// Wert eines Parameters aus "Digest realm="x", nonce="y", algorithm=SHA-256"
inline std::string auth_param(const std::string &h, const std::string &name) {
  size_t p = 0;
  while ((p = h.find(name, p)) != std::string::npos) {
    bool start_ok = p == 0 || h[p - 1] == ' ' || h[p - 1] == ',';
    size_t eq = p + name.size();
    if (start_ok && eq < h.size() && h[eq] == '=') {
      size_t v = eq + 1;
      if (v < h.size() && h[v] == '"') {
        size_t e = h.find('"', v + 1);
        return e == std::string::npos ? "" : h.substr(v + 1, e - v - 1);
      }
      size_t e = h.find(',', v);
      std::string r = h.substr(v, e == std::string::npos ? std::string::npos : e - v);
      while (!r.empty() && r.back() == ' ') r.pop_back();
      return r;
    }
    p = eq;
  }
  return "";
}

// Authorization-Header fuer eine Anfrage nach einer 401-Antwort (WWW-Authenticate) bauen.
inline std::string digest_header(const std::string &www, const std::string &method, const std::string &uri,
                                 const std::string &user, const std::string &password, const std::string &cnonce) {
  const std::string realm = auth_param(www, "realm"), nonce = auth_param(www, "nonce");
  if (realm.empty() || nonce.empty()) return "";
  const std::string nc = "00000001", qop = "auth";
  const std::string ha1 = sha256_hex(user + ":" + realm + ":" + password);
  const std::string ha2 = sha256_hex(method + ":" + uri);
  const std::string resp = sha256_hex(ha1 + ":" + nonce + ":" + nc + ":" + cnonce + ":" + qop + ":" + ha2);
  return "Digest username=\"" + user + "\", realm=\"" + realm + "\", nonce=\"" + nonce + "\", uri=\"" + uri +
         "\", algorithm=SHA-256, response=\"" + resp + "\", qop=" + qop + ", nc=" + nc + ", cnonce=\"" + cnonce + "\"";
}

}  // namespace adnet
