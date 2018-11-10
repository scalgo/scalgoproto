#include "example.h"
#include <iostream>
#include <cstdio>

int main() {
  scalgoproto::Writer w;

  auto desc = w.construct<ModuleDescriptionOut>();
  desc.addSpider(true);
  desc.addSumInputSizeMemoryFactor(14);
  desc.addBaseMemory(1024);

  auto [data, size] = w.finalize(desc);

  for (size_t i=0; i < size; ++i) {
    printf("%02X", (int)((const unsigned char *)data)[i]);
    if ((i & 3) == 3) printf(" ");
  }
  printf("\n");
  scalgoproto::Reader r(data, size);
  auto desc2 = r.root<ModuleDescriptionIn>();
  std::cout << desc2.getSpider() << " " << desc2.getBaseMemory() << std::endl;
  return 0;
}
