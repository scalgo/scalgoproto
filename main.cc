#include "example.h"

int main() {
  scalgoproto::Writer w;

  auto desc = w.construct<ModuleDescriptionOut>();
  desc.addSpider(true);
  desc.addSumInputSizeMemoryFactor(14);
  desc.addBaseMemory(1024);
  return 0;
}
