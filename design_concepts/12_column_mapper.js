var mapper=document.getElementById("mapper");
var pathButtons=document.querySelectorAll("[data-path]");
var statusEl=document.getElementById("detectedStatus");
var rowCount=document.getElementById("rowCount");
var validRows=document.getElementById("validRows");
var sizeRange=document.getElementById("sizeRange");
var passRange=document.getElementById("passRange");
var headerRow=document.getElementById("headerRow");
var headerHint=document.getElementById("headerHint");
var rangeToggle=document.getElementById("rangeToggle");
var rangeGuide=document.getElementById("rangeGuide");
var recordedSize=document.getElementById("recordedSize");
var recordedSecond=document.getElementById("recordedSecond");
var recordedThird=document.getElementById("recordedThird");
var batchResult=document.getElementById("batchResult");
var batchQueue=document.getElementById("batchQueue");
var readyLabel=document.getElementById("readyLabel");
var footerReady=document.getElementById("footerReady");
var importButton=document.getElementById("importButton");
var rangeStage=1;

function rawMode(){
  return mapper.classList.contains("raw-mode");
}

function activeSteps(){
  var selector=rawMode()?".range-progress.raw-only [data-range-step]":".range-progress.processed-only [data-range-step]";
  return document.querySelectorAll(selector);
}

function setProgress(current){
  activeSteps().forEach(function(step){
    var number=Number(step.dataset.rangeStep);
    step.className=number<current?"complete":number===current?"current":"";
  });
}

function resetBatch(){
  batchResult.hidden=true;
  batchQueue.hidden=true;
  readyLabel.textContent="Ready to import";
  footerReady.textContent="1 sample ready.";
  importButton.querySelector("span").textContent="Import sample";
}

function resetRanges(){
  rangeStage=1;
  recordedSize.hidden=true;
  recordedSecond.hidden=true;
  recordedThird.hidden=true;
  document.querySelectorAll(".range-size,.range-pass,.range-empty,.range-full").forEach(function(cell){
    cell.classList.remove("range-size","range-pass","range-empty","range-full");
  });
  if(rawMode()){
    document.getElementById("rangeTitle").textContent="Select the sieve-size values";
    document.getElementById("rangeCopy").textContent="Click the sieve-size column or range for the first candidate.";
    document.getElementById("recordedSizeLabel").textContent="Sieve size";
    document.getElementById("recordedSizeCode").textContent="A4:A11";
    document.getElementById("recordedSecondLabel").textContent="Empty sieve";
    document.getElementById("recordedSecondCode").textContent="B4:B11";
  }else{
    document.getElementById("rangeTitle").textContent="Select the particle-size values";
    document.getElementById("rangeCopy").textContent="Click the highlighted source column to record its numeric range.";
    document.getElementById("recordedSizeLabel").textContent="Particle size";
    document.getElementById("recordedSizeCode").textContent="B6:B20";
    document.getElementById("recordedSecondLabel").textContent="Percent passing";
    document.getElementById("recordedSecondCode").textContent="C6:C20";
  }
  setProgress(1);
  resetBatch();
}

function closeRanges(){
  rangeGuide.classList.remove("on");
  mapper.classList.remove("range-selecting");
  rangeToggle.innerHTML='<i class="fa-regular fa-object-group"></i>Use cell ranges';
  resetRanges();
}

function finishPattern(){
  rangeStage=rawMode()?4:3;
  setProgress(rangeStage);
  document.getElementById("rangeTitle").textContent="Pattern applied to the remaining candidates";
  document.getElementById("rangeCopy").textContent="Each matched dataset was interpreted and validated separately. Any failed match would remain marked for review.";
  batchResult.hidden=false;
  batchQueue.hidden=false;
  readyLabel.textContent="4 samples ready to import";
  footerReady.textContent="4 samples ready.";
  importButton.querySelector("span").textContent="Import 4 samples";
}

function setPath(path){
  var raw=path==="raw";
  mapper.classList.toggle("raw-mode",raw);
  mapper.classList.toggle("processed-mode",!raw);
  pathButtons.forEach(function(button){
    button.classList.toggle("on",button.dataset.path===path);
  });
  statusEl.querySelector("span").textContent=raw?"Raw sieve table detected":"Processed curve detected";
  rowCount.textContent=raw?"8 sieve rows + pan":"15 numeric rows";
  validRows.textContent=raw?"8 rows + pan":"15 rows";
  sizeRange.textContent=raw?"0.063-4.000 mm + pan":"0.00010-0.00172 mm";
  passRange.textContent=raw?"Calculated 0-100%":"0-100%";
  headerRow.value=raw?"3":"5";
  headerHint.innerHTML='<i class="fa-solid fa-check"></i>Row '+headerRow.value+" contains recognizable headings";
  document.querySelector(".processed-curve").style.display=raw?"none":"block";
  document.querySelector(".raw-curve").style.display=raw?"block":"none";
  closeRanges();
}

pathButtons.forEach(function(button){
  button.addEventListener("click",function(){setPath(button.dataset.path);});
});

document.getElementById("applyHeader").addEventListener("click",function(){
  var value=headerRow.value.trim()||"1";
  headerRow.value=value;
  headerHint.innerHTML='<i class="fa-solid fa-check"></i>Mappings kept; preview refreshed from row '+value;
});

rangeToggle.addEventListener("click",function(){
  if(rangeGuide.classList.contains("on")){
    closeRanges();
  }else{
    resetRanges();
    rangeGuide.classList.add("on");
    mapper.classList.add("range-selecting");
    rangeToggle.innerHTML='<i class="fa-solid fa-check"></i>Cell range guide open';
  }
});

document.getElementById("rangeClose").addEventListener("click",closeRanges);
document.getElementById("rangeReset").addEventListener("click",resetRanges);
document.getElementById("reviewMatches").addEventListener("click",function(){
  batchQueue.scrollIntoView({behavior:"smooth",block:"nearest"});
});

function markColumn(selector,className){
  document.querySelectorAll(selector).forEach(function(cell){
    if(!cell.classList.contains("header-row-cell"))cell.classList.add(className);
  });
}

document.querySelectorAll(".processed-data td.size-col,.processed-data td.pass-col").forEach(function(cell){
  cell.addEventListener("click",function(){
    if(!rangeGuide.classList.contains("on")||rawMode())return;
    if(rangeStage===1){
      markColumn(".processed-data td.size-col","range-size");
      recordedSize.hidden=false;
      rangeStage=2;
      setProgress(2);
      document.getElementById("rangeTitle").textContent="Now select the cumulative-passing values";
      document.getElementById("rangeCopy").textContent="Choose the matching numeric range. Both ranges must contain the same number of values.";
    }else if(rangeStage===2){
      markColumn(".processed-data td.pass-col","range-pass");
      recordedSecond.hidden=false;
      finishPattern();
    }
  });
});

document.querySelectorAll(".raw-data td.size-col,.raw-data td.empty-col,.raw-data td.full-col").forEach(function(cell){
  cell.addEventListener("click",function(){
    if(!rangeGuide.classList.contains("on")||!rawMode())return;
    if(rangeStage===1){
      markColumn(".raw-data td.size-col","range-size");
      recordedSize.hidden=false;
      rangeStage=2;
      setProgress(2);
      document.getElementById("rangeTitle").textContent="Now select the empty-sieve weights";
      document.getElementById("rangeCopy").textContent="Choose the matching empty-sieve range for the same rows.";
    }else if(rangeStage===2){
      markColumn(".raw-data td.empty-col","range-empty");
      recordedSecond.hidden=false;
      rangeStage=3;
      setProgress(3);
      document.getElementById("rangeTitle").textContent="Now select sieve + sample";
      document.getElementById("rangeCopy").textContent="Choose the final weight range. All three ranges must contain the same sieve rows.";
    }else if(rangeStage===3){
      markColumn(".raw-data td.full-col","range-full");
      recordedThird.hidden=false;
      finishPattern();
    }
  });
});

document.getElementById("advancedToggle").addEventListener("click",function(){
  var open=!this.classList.contains("open");
  this.classList.toggle("open",open);
  document.getElementById("advancedBody").classList.toggle("open",open);
  this.setAttribute("aria-expanded",open?"true":"false");
});
