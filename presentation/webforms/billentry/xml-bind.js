 
// make this the base url for exist and then have each fetch create url
//var xmlDBBaseUrl = "http://tyrell/exist/rest/db"
//var xmlDBBaseUrl = "http://skyline/exist/rest/db"


//var accountsUrl = xmlDBBaseUrl+"/skyline/bills";

// try and make this a local
// an in memory xml document that represents all available accounts
//var accountsDoc = null;
//var accountSelected = null;

// an in memory xml document that represents all available bills for a given account
//var billsDoc = null;

//var billUrl = null;
// an in memory xml document that represents the entire bill
var billDoc = null;
var billSelected = null;


var httpObject = null;
var appAvailable = false;




// Lots of manual lifting here.  This is due to the fact that JS Frameworks do not do
// a good job of handling XML Namespaces. 
// ToDo: evaluate this function across browsers
function billXML2Array(billDoc)
{

    // build an array based on the bill xml hypothetical charges
    var hc = new Array();
    

    // ToDo: support multiple <ub:details service=*/>
    // bind to chargegroups
    var chargegroup = billDoc.getElementsByTagName("ub:chargegroup");
    for (cg = 0; cg < chargegroup.length; cg++)
    {

        var charges = chargegroup[cg].getElementsByTagName("ub:charges")[0];
        if (charges.attributes[0].nodeValue == "actual")
        {

            var charge = charges.getElementsByTagName("ub:charge");
            for(c = 0; c < charge.length; c++)
            {

                hc[c] = new Array();

                hc[c][0] = chargegroup[cg].attributes[0].nodeValue;

                var descriptionElem = (charge[c].getElementsByTagName("ub:description"))[0];
                hc[c][1] = descriptionElem && descriptionElem.childNodes[0].nodeValue ? descriptionElem.childNodes[0].nodeValue : null;

                var quantityElem = (charge[c].getElementsByTagName("ub:quantity"))[0];
                hc[c][2] = quantityElem && quantityElem.childNodes[0] ? quantityElem.childNodes[0].nodeValue : null;
                hc[c][3] = quantityElem && quantityElem.attributes[0] ? quantityElem.attributes[0].nodeValue : null;

                var rateElem = (charge[c].getElementsByTagName("ub:rate"))[0];
                hc[c][4] = rateElem && rateElem.childNodes[0] ? rateElem.childNodes[0].nodeValue : null;
                hc[c][5] = rateElem && rateElem.attributes[0] ? rateElem.attributes[0].nodeValue : null;

                var totalElem = (charge[c].getElementsByTagName("ub:total"))[0];
                hc[c][6] = totalElem && totalElem.childNodes[0].nodeValue ? totalElem.childNodes[0].nodeValue : null;

            }
        }
    }

    return hc;
}


// ToDo: evaluate this function across browsers
// records passed in must be ordered by chargegroup, as they are by the GroupingStore
function Array2BillXML(bill, records)
{

    // enumerate the records
    // for each chargegroup encountered, find the actual charges in xml
    // delete those actual charges
    // reconstruct the actual charges from the records
    // and insert them into the chargegroup

    // given the array of records from the store backing
    // the grid, convert them to XML
 
    // used to track each new chargegroup found in the groupingstore records
    var cg = null;
    // used to track the XML charges that are deleted then recreated
    var charges = null;
    // used to track charges total. see below where it is added to the charges.
    var chargesSubtotal = 0;
    var chargesTotalElem = null;

    for(r = 0; r < records.length; r++)
    {
        // pick the current record from the grid grouping store and turn it into XML
        var curRec = records[r];

        // a new chargegroup is seen
        if (cg != curRec.data.chargegroup) 
        {
            cg = curRec.data.chargegroup;

            // reset the total
            chargesSubtotal = 0;

            // ToDo: must support multiple <ub:details service=*/>
            // find the associated actual charges
            var actualChargesNodeList = evaluateXPath(bill, 
                "/ub:bill/ub:details/ub:chargegroup[@type=\""+cg+"\"]/ub:charges[@type=\"actual\"]");

            // ToDo: assert only one set of charges came back
            charges = actualChargesNodeList[0];

            // remove only the charge item children leaving the total child behind
            var deleteChildrenNodeList = evaluateXPath(charges, "ub:charge");
            for (i = 0; i < deleteChildrenNodeList.length; i++)
            {
                charges.removeChild(deleteChildrenNodeList[i]);
            }

            // Get the total element
            // ToDo: assert only one is returned
            chargesTotalElem = evaluateXPath(charges, "ub:total")[0];
            
        }

        // for the currently obtained charges element, add a new child for every iteration of r
        // when a new chargegroup is encountered, set charges to the new set of charges

        // once removed, recreate each charge
        var charge = bill.createElementNS("bill","ub:charge");

        // and the children of each charge
        var description = bill.createElementNS("bill", "ub:description")
        description.appendChild(bill.createTextNode(curRec.data.description));
        charge.appendChild(description);

        var quantity = bill.createElementNS("bill", "ub:quantity");
        quantity.setAttribute("units", curRec.data.quantityunits);
        quantity.appendChild(bill.createTextNode(curRec.data.quantity));
        charge.appendChild(quantity);

        var rate = bill.createElementNS("bill", "ub:rate");
        rate.setAttribute("units", curRec.data.rateunits);
        rate.appendChild(bill.createTextNode(curRec.data.rate));
        charge.appendChild(rate);

        var total = bill.createElementNS("bill", "ub:total");
        total.appendChild(bill.createTextNode(curRec.data.total));
        charge.appendChild(total);

        // finally, add the charge to the current set of charges
        charges.insertBefore(charge, chargesTotalElem);

        // accumulate the total.  Don't like to do this here...
        // Appears to be no good way to get the grouping store group totals
        // So, we totalize here, or forget it and let a downstream program
        // add the totals to the XML doc.
        // avoid float rounding by going integer math
        chargesSubtotal += parseFloat(curRec.data.total*100);
        chargesTotalElem.removeChild(chargesTotalElem.firstChild);
        chargesTotalElem.appendChild(bill.createTextNode((chargesSubtotal/100).toString()));
    }

    return bill;
}




 /*function bindXML()
 {


    // using low level API since high level API does not support PUT
    jQuery.ajax({
      url: accountsUrl,
      type: "GET",
      processData: false,
      data: accountsDoc,
      dataType: "xml",
      success: handleAccountsDoc_GET,
      error: handleXML_GET_error
    });
}
*/

/*
function handleAccountsDoc_GET(data)
{
  accountsDoc = data;
  // bind to returned accounts (from exist)
  // one collection named /db is expected with the children being the accounts
  var accounts = evaluateXPath(accountsDoc, "/exist:result/exist:collection[@name=\"/db/skyline/bills\"]/exist:collection");

  $("#accountsForm").empty();
  $("#accountsForm").append("<select id=\"accountsFormSelect\" onChange=\"javascript:fetchBills(accountSelected = this.value);\"")
  $("#accountsFormSelect").append("<option>---------</option>");
  for (var i = 0; i < accounts.length; i++)
  {
    $("#accountsFormSelect").append("<option >"+accounts[i].getAttribute("name")+"</option>");
  }

}
*/

function handleXML_GET_error(xhr, status, error)
{
  // ToDo: put into document body
  alert(status);
  alert("readyState: "+xhr.readyState+"\nstatus: "+xhr.status);
  alert("responseText: "+xhr.responseText);
}


function handleXML_PUT(data, status, req)
{
  // never make it here due to a bug(?) in JQuery and the way its xmlparser handles server return values
  alert("PUT " + data);
}

function handleXML_PUT_error(xhr, status, error)
{
  if (status == "parsererror")
  {
    // http://james.revillini.com/2006/10/27/no-element-found-in-firebug-or-firefox-javascript-console/
    // probably need to determine how to check that PUT completed successfully (which if it does, the server return data still causes a failure in jquery)
    alert(status);
  } else {
    alert(status);
    alert("readyState: "+xhr.readyState+"\nstatus: "+xhr.status);
    alert("responseText: "+xhr.responseText);
  }
}

function fetchBills(account)
{
  // when account is selected, update available bills
  var billsUrl = accountsUrl + "/" + account;
  // using low level API since high level API does not support PUT
  jQuery.ajax({
    url: billsUrl,
    type: "GET",
    processData: false,
    data: billsDoc,
    dataType: "xml",
    success: handleBillsDoc_GET,
    error: handleXML_GET_error
  });
}

function handleBillsDoc_GET(data)
{
  billsDoc = data;
  // bind to returned bills (from exist)
  var bills = evaluateXPath(billsDoc, "/exist:result/exist:collection/exist:resource");

  $("#billsForm").empty();
  $("#billsForm").append("<select id=\"billsFormSelect\" onChange=\"javascript:fetchBill(billSelected = this.value);\"")
  $("#billsFormSelect").append("<option>---------</option>");
  for (var i = 0; i < bills.length; i++)
  {
    $("#billsFormSelect").append("<option >"+bills[i].getAttribute("name")+"</option>");
  }
}


// retrieve the bill xml document and store it as an in memory xml document.
function fetchBill(bill)
{

  //billUrl = accountsUrl + "/" + accountSelected + "/" + billSelected;
  billUrl = bill;
  // using low level API since high level API does not support PUT
  // ToDo: rename xml_get to bill oriented function name
  jQuery.ajax({
    url: billUrl,
    type: "GET",
    processData: false,
    data: billDoc,
    dataType: "xml",
    success: handleBillDoc_GET,
    error: handleXML_GET_error
  });

}

function handleBillDoc_GET(data)
{
  billDoc = data;
  bindBillDocStatic();
  bindBillDocForms();
}



// given bill xml, bind it to the forms
function bindBillDocForms()
{
  // there will be more than one form eventually
  bindDetails();
}


function bindDetails()
{
  // remove previously created form
  $("#billForm").empty();

  // copy template table into form for population
  $("#billForm").append($("#formDetails-template").clone().attr("id", "formDetails"));


  // bind to chargegroups
  var chargegroup = billDoc.getElementsByTagName("ub:chargegroup");
  for (cg = 0; cg < chargegroup.length; cg++)
  {
    var formChargegroup = $("#formChargegroup-template").clone().attr("id", "formChargegroup-"+cg);
    $("#formDetails").append(formChargegroup);

    var charges = chargegroup[cg].getElementsByTagName("ub:charges")[0];
    if (charges.attributes[0].nodeValue == "actual")
    {

      var charge = charges.getElementsByTagName("ub:charge");
      for(i = 0; i < charge.length; i++)
      {

        var formCharge = $("#formCharge-template").clone().attr("id", "formCharge-"+cg+"-"+i);
        $("#formChargegroup-"+cg).append(formCharge);

        var chargeFields = $("#formCharge-"+cg+"-"+i+" td");

        // ToDo: it would be nice to be able to refer to the columns symbolically
        chargeFields.slice(0,1).append("<a href=\"javascript:insertChargeAbove('"+getElementXPath(charge[i])+"'); \">Insert Above</a>&nbsp;");
        chargeFields.slice(1,2).append("<a href=\"javascript:deleteCharge('"+getElementXPath(charge[i])+"');\">Delete</a>&nbsp;");
        chargeFields.slice(2,3).append("<a href=\"javascript:insertChargeBelow('"+getElementXPath(charge[i])+"');\">Insert Below</a>");

        var description = (charge[i].getElementsByTagName("ub:description"))[0];
        if (description)
        {
          var descriptionText = "Enter Description";
          if(description.childNodes[0] != undefined)
            descriptionText = description.childNodes[0].nodeValue;
          chargeFields.slice(3,4).append("<input type=\"textfield\" name=\"" + getElementXPath(description) + "\" value=\"" + descriptionText + "\" onChange=\"javascript:storeData(this.name, this.value);\">");
        }

        var quantityElem = (charge[i].getElementsByTagName("ub:quantity"))[0];
        if (quantityElem)
        {
          var quantityText = "Enter Quantity";
          if (quantityElem.childNodes[0] != undefined)
            quantityText = quanityText = quantityElem.childNodes[0].nodeValue;
          var quantityUnitsAttr = quantityElem.attributes["units"];
          var quantityUnitsText = quantityElem.getAttribute("units");

          // ToDo: it would be nice to be able to refer to the columns symbolically
          chargeFields.slice(4,5).append("<input type=\"textfield\" name=\"" + getElementXPath(quantityElem) + "\" value=\"" + quantityText +  "\" onChange=\"javascript:storeData(this.name, this.value);\">");

          // handle quantity units attribute
          var opts = ["none", "kWh","Therms", "cents", "dollars", "KWD", "Ccf"];  // ToDo: pull from db
          chargeFields.slice(5,6).append("<select id=\"select-1-"+cg+"-"+i+"\" name=\"" + getElementXPath(quantityUnitsAttr) + "\" onChange=\"javascript:storeData(this.name, this.value);\">");
          opts.forEach(
            function(opt)
            {
              $("#select-1-"+cg+"-"+i).append("<option "+((quantityUnitsText == opt)?"selected":"")+">"+opt+"</option>");
            }
          );
        } else {
          // ToDo: it would be nice to be able to refer to the columns symbolically
          chargeFields.slice(4,5).append("<a href=\"javascript:insertQuantity('"+getElementXPath(charge[i])+"');\">Add Quantity</a>");
        }


        var rateElem = (charge[i].getElementsByTagName("ub:rate"))[0];
        if (rateElem)
        {
          var rateText = "Enter Rate";
          if (rateElem.childNodes[0] != undefined)
            rateText = rateElem.childNodes[0].nodeValue;
          var rateUnitsAttr = rateElem.attributes["units"];
          var rateUnitsText = rateElem.getAttribute("units");

          chargeFields.slice(6,7).append("<input type=\"textfield\" name=\"" + getElementXPath(rateElem) + "\" value=\"" + rateText + "\" onChange=\"javascript:storeData(this.name, this.value);\">");

          // handle quantity units attribute
          var opts = ["none", "dollars", "cents", "percent"];  // ToDo: pull from db
          chargeFields.slice(7,8).append("<select id=\"select-2-"+cg+"-"+i+"\" name=\"" + getElementXPath(rateUnitsAttr) + "\" onChange=\"javascript:storeData(this.name, this.value);\">");
          opts.forEach(
            function(opt)
            {
              $("#select-2-"+cg+"-"+i).append("<option "+((rateUnitsText == opt)?"selected":"")+">"+opt+"</option>");
            }
          );
        } else {
          // ToDo: it would be nice to be able to refer to the columns symbolically
          chargeFields.slice(6,7).append("<a href=\"javascript:insertRate('"+getElementXPath(charge[i])+"');\">Add rate</a>");
        }

        var totalElem = (charge[i].getElementsByTagName("ub:total"))[0];
        if (totalElem)
        {
          var totalText = "Enter Total";
          if(totalElem.childNodes[0] != undefined)
            totalText = totalElem.childNodes[0].nodeValue;
          chargeFields.slice(8,9).append("<input type=\"textfield\" name=\"" + getElementXPath(totalElem) + "\" value=\"" + totalText + "\" onChange=\"javascript:storeData(this.name, this.value);\">");
        } else {
          // print link to add quantity Element
        }

        // all preceding charges plus this charge
        var runningChargesXPath = getElementXPath(charge[i]) + "/preceding-sibling::*/ub:total | " + getElementXPath(charge[i]) + "/ub:total";
        var runningChargesTotal = evaluateXPath(billDoc, "round(sum("+runningChargesXPath+")*100) div 100");

        chargeFields.slice(9,10).append(runningChargesTotal);

      }

      // chargegroup subtotal
      var formCharge = $("#formCharge-template").clone().attr("id", "formCharge-"+cg+"-subtotal");
      $("#formChargegroup-"+cg).append(formCharge);

      var chargesTotalElem = evaluateXPath(billDoc, getElementXPath(charges)+"/ub:total")[0];

      if (chargesTotalElem)
      {
        var chargesTotalText = "";
        if(chargesTotalElem.childNodes[0] != undefined)
          chargesTotalText = chargesTotalElem.childNodes[0].nodeValue;
        $("#formCharge-"+cg+"-subtotal td").slice(8,9).append("<input type=\"textfield\" name=\"" + getElementXPath(chargesTotalElem) + "\" value=\"" + chargesTotalText + "\" onChange=\"javascript:storeData(this.name, this.value);\">");
      }
    }
  }
  $("#billForm").append("<input type=\"submit\" action=\"submit\"></input>");
  $("#billForm").prepend("<input type=\"submit\" action=\"submit\"></input>");
}

// uneditable bill fields
function bindBillDocStatic()
{
  $("#billId").empty();
  $("#billPath").empty();
  $("#addressee").empty();
  var bill = billDoc.getElementsByTagName("ub:bill");
  if (bill)
  {

    var id = bill[0].getAttribute("id");
    $("#billId").append(id);
  }
  $("#billPath").append(billUrl);


  var car = billDoc.getElementsByTagName("ub:billingaddress");
  if (car)
  {
    var addressee = car[0].getElementsByTagName("ub:addressee");
    $("#addressee").append(addressee[0].childNodes[0].nodeValue);
  }

}


function insertQuantity(xpath)
{
  var node = evaluateXPath(billDoc, xpath);
  // find the sibling quantity gets inserted before
  var quantity = billDoc.createElementNS("bill","ub:quantity");
  quantity.appendChild(billDoc.createTextNode("Enter Quantity"));

  var units = billDoc.createAttribute("units");

  quantity.setAttributeNode(units);
  var rateSibling = evaluateXPath(billDoc, xpath+"/ub:rate");
  if (rateSibling.length == 1)
  {
    rateSibling[0].parentNode.insertBefore(quantity, rateSibling[0]);
    bindDetails();
    return;
  }
  var totalSibling = evaluateXPath(billDoc, xpath+"/ub:total");
  if (totalSibling.length == 1)
  {
    totalSibling[0].parentNode.insertBefore(quantity, totalSibling[0]);
    bindDetails();
    return;
  }
}

function insertRate(xpath)
{
  var node = evaluateXPath(billDoc, xpath);

  // find the sibling quantity gets inserted before
  var rate = billDoc.createElementNS("bill","ub:rate");
  rate.appendChild(billDoc.createTextNode("Enter Rate"));

  var units = billDoc.createAttribute("units");

  rate.setAttributeNode(units);
  var totalSibling = evaluateXPath(billDoc, xpath+"/ub:total");
  if (totalSibling.length == 1)
  {
    totalSibling[0].parentNode.insertBefore(rate, totalSibling[0]);
    bindDetails();
    return;
  }
}


function insertChargeAbove(xpath)
{

  var node = evaluateXPath(billDoc, xpath);
  // check to ensure path pointed to a node

  var charge = makeChargeGrove();

  node[0].parentNode.insertBefore(charge, node[0]);

  bindDetails();

}

function insertChargeBelow(xpath)
{

  var node = evaluateXPath(billDoc, xpath);
  // check to ensure path pointed to a node

  var charge = makeChargeGrove();

  node[0].parentNode.insertBefore(charge, node[0].nextSibling);

  bindDetails();

}

function makeChargeGrove()
{
  var charge = billDoc.createElementNS("bill","ub:charge");
  var chargeDescription = billDoc.createElementNS("bill", "ub:description")
  chargeDescription.appendChild(billDoc.createTextNode("Enter description"));
  charge.appendChild(chargeDescription);

  //var chargeQuantity = billDoc.createElementNS("bill", "ub:quantity");
  //chargeQuantity.appendChild(billDoc.createTextNode("Quantity"));
  //charge.appendChild(chargeQuantity);

  //var chargeRate = billDoc.createElementNS("bill", "ub:rate");
  //chargeRate.appendChild(billDoc.createTextNode("Rate"));
  //charge.appendChild(chargeRate);

  var chargeTotal = billDoc.createElementNS("bill", "ub:total");
  chargeTotal.appendChild(billDoc.createTextNode("0.0"));
  charge.appendChild(chargeTotal);

  return charge;
}

function deleteCharge(xpath)
{

  var node = evaluateXPath(billDoc, xpath);
  // check to ensure path pointed to a node

  node[0].parentNode.removeChild(node[0]);

  bindDetails();

}


function submitBill(form)
{
  jQuery.ajax({
    url: billUrl,
    type: "PUT",
    processData: false,
    contentType: "text/xml",
    data: billDoc,
    success: handleXML_PUT,
    error: handleXML_PUT_error
  });

}


// pass in an xml doc to make this generic?  would need to pass in the doc and callback to bind data
function storeData(xpath, value)
{

  var node = evaluateXPath(billDoc, xpath);

  if (node[0].nodeType == 1) // element
  {
    // should a value be passed in for an xpath, ensure a descendent text node exists
    if (node[0].childNodes[0] == undefined)
      node[0].appendChild(billDoc.createTextNode(""));
    node[0].childNodes[0].nodeValue = value;
  } else if (node[0].nodeType == 2) { // attribute

    var parent = node[0].ownerElement;
    parent.setAttribute(node[0].nodeName, value);
  }

  bindBillDocForms();
}
